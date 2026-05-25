from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.settings import read_settings
from app.db.models import ChatMessage, Event, Extraction, Person, Relationship
from app.extraction.applier import apply_extraction
from app.llm.client import LLMClient
from app.matching import person_matches_text

AUTO_APPLY_KINDS = {"event_new", "person_new", "note_new", "person_update"}


def run_extraction_for_session(db: Session, session_id: int) -> dict[str, int]:
    existing = db.scalars(select(Extraction).where(Extraction.session_id == session_id)).all()
    if existing:
        return _summary(existing)

    messages = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc())).all()
    user_text = "\n".join(message.content for message in messages if message.role == "user")
    people = _mentioned_people(db, user_text, messages)
    settings = read_settings(db)
    rows = _build_model_extractions(db, session_id, settings, messages) or _build_extractions(session_id, user_text, people)

    for row in rows:
        if _should_auto_apply(row.kind, row.confidence, settings):
            apply_extraction(db, row)
            row.status = "auto_applied"
        db.add(row)
    db.commit()
    return _summary(rows)


def _build_model_extractions(db: Session, session_id: int, settings: dict[str, Any], messages: list[ChatMessage]) -> list[Extraction] | None:
    model = settings.get("extraction_model", "anthropic/claude-haiku-4-5-20251001")
    output = LLMClient().complete_json(model, _extraction_messages(messages))
    if output is None:
        return None
    people = db.scalars(select(Person).order_by(Person.importance.desc(), Person.name.asc())).all()
    relationships = db.scalars(select(Relationship).order_by(Relationship.id.asc())).all()
    return _model_output_to_extractions(session_id, output, people, relationships)


def _extraction_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    rendered = "\n".join(f"{message.role}: {message.content}" for message in messages)
    prompt = (
        "你是用户的关系图谱抽取助手。只输出 JSON，无任何解释。\n"
        "识别本次对话中的人物、实体、事件、关系变化和用户自身画像更新。\n\n"
        f"# 本次对话内容\n{rendered}"
    )
    return [{"role": "user", "content": prompt}]


def _model_output_to_extractions(session_id: int, output: dict[str, Any], people: list[Person], relationships: list[Relationship]) -> list[Extraction]:
    rows = []
    for item in output.get("people") or []:
        if item.get("is_new") and not item.get("matched_person_id"):
            facts = item.get("new_facts") or {}
            rows.append(
                Extraction(
                    session_id=session_id,
                    kind="person_new",
                    payload={
                        "name": item["name_used"],
                        "bio": facts.get("bio"),
                        "profile_json": facts.get("profile_json"),
                    },
                    confidence=item.get("confidence"),
                    status="pending",
                )
            )
        elif item.get("matched_person_id") and (item.get("new_facts") or {}).get("profile_json") is not None:
            rows.append(
                Extraction(
                    session_id=session_id,
                    kind="person_update",
                    payload={
                        "person_id": item["matched_person_id"],
                        "profile_json": item["new_facts"]["profile_json"],
                    },
                    confidence=item.get("confidence"),
                    status="pending",
                )
            )
    for item in output.get("entities") or []:
        rows.append(
            Extraction(
                session_id=session_id,
                kind="entity_new",
                payload={
                    "type": item.get("type", "org"),
                    "name": item["name"],
                    "bio": item.get("bio"),
                    "profile_json": item.get("profile_json"),
                },
                confidence=item.get("confidence"),
                status="pending",
            )
        )
    for item in output.get("events") or []:
        participants = [
            {"type": participant.get("type"), "id": participant.get("matched_id")}
            for participant in item.get("participants") or []
            if participant.get("type") and participant.get("matched_id")
        ]
        rows.append(
            Extraction(
                session_id=session_id,
                kind="event_new",
                payload={
                    "occurred_at": item.get("occurred_at"),
                    "title": item["title"],
                    "description": item.get("description"),
                    "participants": participants,
                    "source": "chat_extraction",
                    "source_session_id": session_id,
                },
                confidence=item.get("confidence"),
                status="pending",
            )
        )
    for item in output.get("relationships") or []:
        to_id = _relationship_target_id(item.get("to_id_or_name"), people)
        if to_id is None:
            continue
        if item.get("change_kind") == "update":
            relationship_id = _relationship_update_target_id(item, to_id, relationships)
            if relationship_id is None:
                continue
            rows.append(
                Extraction(
                    session_id=session_id,
                    kind="relationship_update",
                    payload={"relationship_id": relationship_id, **_relationship_update_delta(item.get("delta") or {})},
                    confidence=item.get("confidence"),
                    status="pending",
                )
            )
            continue
        if item.get("change_kind") != "new":
            continue
        rows.append(
            Extraction(
                session_id=session_id,
                kind="relationship_new",
                payload={
                    "from_type": item.get("from_type", "self"),
                    "from_id": item.get("from_id"),
                    "to_type": item.get("to_type", "person"),
                    "to_id": to_id,
                    "relation_type": item["relation_type"],
                    "role": item.get("role"),
                    "notes": (item.get("delta") or {}).get("notes"),
                },
                confidence=item.get("confidence"),
                status="pending",
            )
        )
    self_updates = output.get("self_updates") or {}
    if self_updates.get("patches"):
        rows.append(
            Extraction(
                session_id=session_id,
                kind="self_update",
                payload={"patches": self_updates["patches"]},
                confidence=self_updates.get("confidence"),
                status="pending",
            )
        )
    return rows


def _relationship_update_target_id(item: dict[str, Any], to_id: int, relationships: list[Relationship]) -> int | None:
    matches = [
        relationship
        for relationship in relationships
        if relationship.from_type == item.get("from_type", "self")
        and relationship.from_id == item.get("from_id")
        and relationship.to_type == item.get("to_type", "person")
        and relationship.to_id == to_id
        and relationship.relation_type == item.get("relation_type")
    ]
    return matches[0].id if len(matches) == 1 else None


def _relationship_update_delta(delta: dict[str, Any]) -> dict[str, Any]:
    allowed = {"relation_type", "role", "strength", "status", "notes", "started_at", "ended_at"}
    return {key: value for key, value in delta.items() if key in allowed}


def _relationship_target_id(value: Any, people: list[Person]) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    for person in people:
        if person_matches_text(person.name, person.aliases, value):
            return person.id
    return None


def _build_extractions(session_id: int, text: str, people: list[Person]) -> list[Extraction]:
    rows = []
    if not people and _mentions_boss_relationship(text):
        rows.append(
            Extraction(
                session_id=session_id,
                kind="person_new",
                payload={
                    "name": "老板",
                    "aliases": ["我老板"],
                    "bio": "从聊天内容抽取，需人工确认。",
                },
                confidence=0.8,
                status="pending",
            )
        )
    if people and _mentions_event(text):
        person = people[0]
        rows.append(
            Extraction(
                session_id=session_id,
                kind="event_new",
                payload={
                    "occurred_at": date.today().isoformat(),
                    "title": f"{person.name}提到加班不够",
                    "description": text,
                    "participants": [{"type": "person", "id": person.id}],
                    "source": "chat_extraction",
                    "source_session_id": session_id,
                },
                confidence=0.9,
                status="pending",
            )
        )
    if people and _mentions_boss_relationship(text):
        person = people[0]
        rows.append(
            Extraction(
                session_id=session_id,
                kind="relationship_new",
                payload={
                    "from_type": "self",
                    "from_id": None,
                    "to_type": "person",
                    "to_id": person.id,
                    "to_name": person.name,
                    "relation_type": "上下级",
                    "role": "老板",
                    "notes": "从聊天内容抽取，需人工确认。",
                },
                confidence=0.95,
                status="pending",
            )
        )
    if "被催" in text or "怕被催" in text:
        rows.append(
            Extraction(
                session_id=session_id,
                kind="self_update",
                payload={"patches": {"sensitivities": ["被催"]}},
                confidence=0.7,
                status="pending",
            )
        )
    return rows


def _mentioned_people(db: Session, text: str, messages: list[ChatMessage]) -> list[Person]:
    ids = []
    for message in messages:
        for person in (message.context_used or {}).get("people", []):
            person_id = person.get("id")
            if isinstance(person_id, int) and person_id not in ids:
                ids.append(person_id)
    people_by_context = [person for person_id in ids if (person := db.get(Person, person_id)) is not None]
    if people_by_context:
        return people_by_context
    people = db.scalars(select(Person).order_by(Person.importance.desc(), Person.name.asc())).all()
    return [person for person in people if _person_mentioned(person, text)]


def _person_mentioned(person: Person, text: str) -> bool:
    return person_matches_text(person.name, person.aliases, text)


def _mentions_event(text: str) -> bool:
    return any(keyword in text for keyword in ("加班不够", "进度", "提醒"))


def _mentions_boss_relationship(text: str) -> bool:
    return "老板" in text or "直属上级" in text


def _should_auto_apply(kind: str, confidence: float | None, settings: dict[str, Any]) -> bool:
    configured_kinds = settings.get("auto_extract_kinds") or []
    threshold = float(settings.get("auto_extract_threshold") or 0.85)
    return kind in AUTO_APPLY_KINDS and kind in configured_kinds and (confidence or 0) >= threshold


def _summary(rows: list[Extraction]) -> dict[str, int]:
    return {
        "created": len(rows),
        "auto_applied": sum(1 for row in rows if row.status == "auto_applied"),
        "pending": sum(1 for row in rows if row.status == "pending"),
    }
