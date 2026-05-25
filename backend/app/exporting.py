from __future__ import annotations

import json
import os
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.common import model_dict
from app.config import get_settings
from app.db.models import AppSetting, Entity, Event, Extraction, LifeStage, Note, Person, Relationship, SelfProfile


def build_export_snapshot(db: Session) -> dict[str, Any]:
    return {
        "self": model_dict(db.get(SelfProfile, 1)) if db.get(SelfProfile, 1) else None,
        "people": [model_dict(item) for item in db.scalars(select(Person).order_by(Person.name.asc())).all()],
        "entities": [model_dict(item) for item in db.scalars(select(Entity).order_by(Entity.name.asc())).all()],
        "relationships": [model_dict(item) for item in db.scalars(select(Relationship).order_by(Relationship.id.asc())).all()],
        "events": [model_dict(item) for item in db.scalars(select(Event).order_by(Event.occurred_at.asc())).all()],
        "stages": [model_dict(item) for item in db.scalars(select(LifeStage).order_by(LifeStage.sort_order.asc(), LifeStage.started_at.asc())).all()],
        "notes": [model_dict(item) for item in db.scalars(select(Note).order_by(Note.id.asc())).all()],
        "extractions": [model_dict(item) for item in db.scalars(select(Extraction).order_by(Extraction.id.asc())).all()],
    }


def build_export_zip(db: Session) -> bytes:
    checkpoint_sqlite(db)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dossier.json", json.dumps(build_export_snapshot(db), ensure_ascii=False, indent=2))
        archive.writestr("schema.sql", build_schema_sql(db))
        archive.writestr("config.redacted.json", json.dumps(build_redacted_config(db), ensure_ascii=False, indent=2))
        for person in db.scalars(select(Person).order_by(Person.name.asc())).all():
            archive.writestr(f"people/{safe_name(person.name)}.md", render_person_markdown(db, person))
        data_root = export_data_root()
        if data_root and data_root.exists():
            write_data_dir(archive, data_root)
    return buffer.getvalue()


def export_obsidian(db: Session, root: Path) -> dict[str, int]:
    people_dir = root / "people"
    people_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for person in db.scalars(select(Person).order_by(Person.name.asc())).all():
        (people_dir / f"{safe_name(person.name)}.md").write_text(render_person_markdown(db, person), encoding="utf-8")
        count += 1
    return {"people": count}


def render_person_markdown(db: Session, person: Person) -> str:
    relationships = db.scalars(
        select(Relationship).where(
            ((Relationship.from_type == "person") & (Relationship.from_id == person.id))
            | ((Relationship.to_type == "person") & (Relationship.to_id == person.id))
        )
    ).all()
    events = [
        event
        for event in db.scalars(select(Event).order_by(Event.occurred_at.desc())).all()
        if any(participant.get("type") == "person" and participant.get("id") == person.id for participant in event.participants or [])
    ]
    notes = db.scalars(select(Note).where(Note.target_type == "person", Note.target_id == person.id).order_by(Note.id.asc())).all()
    lines = [
        "---",
        "type: person",
        f"name: {person.name}",
        f"aliases: [{', '.join(person.aliases or [])}]",
        f"importance: {person.importance or 0}",
        "---",
        "",
        f"# {person.name}",
        "",
        "## 画像",
        person.bio or "",
        "",
        json.dumps(person.profile_json or {}, ensure_ascii=False, indent=2),
        "",
        "## 关系",
    ]
    lines.extend(_relationship_lines(db, person, relationships))
    lines.extend(["", "## 最近事件"])
    lines.extend(_event_lines(events))
    lines.extend(["", "## 笔记"])
    lines.extend([f"- {note.content}" for note in notes] or ["- 暂无"])
    lines.append("")
    return "\n".join(lines)


def _relationship_lines(db: Session, current_person: Person, relationships: list[Relationship]) -> list[str]:
    if not relationships:
        return ["- 暂无"]
    return [f"- {item.relation_type}：{_relationship_person_label(db, current_person, item)}，角色：{item.role or '未设置角色'}" for item in relationships]


def _relationship_person_label(db: Session, current_person: Person, relationship: Relationship) -> str:
    if relationship.from_type == "person" and relationship.from_id != current_person.id:
        return _person_link(db, relationship.from_id)
    if relationship.to_type == "person" and relationship.to_id != current_person.id:
        return _person_link(db, relationship.to_id)
    if relationship.from_type == "self" or relationship.to_type == "self":
        return "我"
    return "未关联对象"


def _person_link(db: Session, person_id: int | None) -> str:
    if person_id is None:
        return "未知人物"
    person = db.get(Person, person_id)
    if person is None:
        return f"未知人物 {person_id}"
    return f"[[{person.name}]]"


def _event_lines(events: list[Event]) -> list[str]:
    if not events:
        return ["- 暂无"]
    return [f"- [[{event.occurred_at.isoformat() if event.occurred_at else '未知日期'}]] {event.title}" for event in events]


def sqlite_database_path() -> Path | None:
    database_url = os.getenv("DATABASE_URL") or get_settings().database_url
    if not database_url.startswith("sqlite:///"):
        return None
    raw_path = database_url.removeprefix("sqlite:///")
    return Path(raw_path)


def checkpoint_sqlite(db: Session) -> None:
    try:
        db.execute(text("PRAGMA wal_checkpoint(FULL)"))
    except Exception:
        pass


def export_data_root() -> Path | None:
    database_path = sqlite_database_path()
    if database_path is not None:
        return database_path.parent
    upload_dir = Path(os.getenv("UPLOAD_DIR", get_settings().upload_dir))
    return upload_dir.parent


def write_data_dir(archive: zipfile.ZipFile, data_root: Path) -> None:
    for path in sorted(data_root.rglob("*")):
        if path.is_file():
            archive.write(path, f"data/{path.relative_to(data_root).as_posix()}")


def build_redacted_config(db: Session) -> dict[str, Any]:
    env = {
        "DATABASE_URL": os.getenv("DATABASE_URL", get_settings().database_url),
        "UPLOAD_DIR": os.getenv("UPLOAD_DIR", get_settings().upload_dir),
        "EXPORT_DIR": os.getenv("EXPORT_DIR", get_settings().export_dir),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", get_settings().ollama_base_url),
    }
    app_settings = {row.key: row.value for row in db.scalars(select(AppSetting).order_by(AppSetting.key.asc())).all()}
    return {"env": redact_config(env), "app_settings": redact_config(app_settings)}


def redact_config(value: Any, key: str = "") -> Any:
    if should_redact(key):
        return "***REDACTED***" if value else value
    if isinstance(value, dict):
        return {item_key: redact_config(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_config(item, key) for item in value]
    return value


def should_redact(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("api_key", "token", "secret", "password"))


def build_schema_sql(db: Session) -> str:
    rows = db.execute(
        text(
            """
            SELECT sql
            FROM sqlite_master
            WHERE sql IS NOT NULL
            ORDER BY type, name
            """
        )
    ).scalars()
    return "\n\n".join(rows) + "\n"


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_")
