from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import ok
from app.api.settings import read_settings
from app.db.models import Extraction, Person, Relationship
from app.db.session import get_db
from app.extraction.runner import _model_output_to_extractions
from app.import_documents import write_import_markdown
from app.llm.client import LLMClient
from app.matching import person_matches_text
from app.parsers.files import parse_import_file

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_CHARS_PER_CHUNK = 4000


LLM_PROMPT_TEMPLATE = """请回顾我们到目前为止的所有对话历史，梳理出其中提到的所有人、公司/组织、和重要事件。
我需要你按照下面的 JSON 格式输出，不要任何额外解释。

{
  "people": [{"name": "人名", "aliases": ["别名1"], "bio": "一句话简介", "profile": {}}],
  "entities": [{"type": "company|family|friend_group|org", "name": "...", "bio": "...", "members": ["人名1"]}],
  "events": [{"occurred_at": "YYYY-MM-DD", "title": "...", "description": "...", "participants": ["人名"]}],
  "self": {"communication_style": "...", "sensitivities": ["..."], "goals": ["..."]}
}
"""


class LLMMemoryImport(BaseModel):
    memory_json: str = Field(alias="json")


@router.post("/file")
async def import_file(
    file: UploadFile,
    target_type: str | None = Form(default=None),
    target_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if len(data) > MAX_IMPORT_FILE_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 10MB limit")
    try:
        content = parse_import_file(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    source_document = write_import_markdown(
        "file_import",
        file.filename or "imported-file",
        content,
        {"source_file": file.filename or "", "target_type": target_type or "self", "target_id": target_id},
    )
    chunks = chunk_text(content, MAX_IMPORT_CHARS_PER_CHUNK)
    rows = file_chunks_to_extractions(db, chunks, file.filename or "", target_type, target_id)
    for row in rows:
        db.add(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return ok({"created": len(rows), "ids": [row.id for row in rows], "source_document": source_document})


@router.post("/llm-memory")
def import_llm_memory(payload: LLMMemoryImport, db: Session = Depends(get_db)):
    source_document = write_import_markdown("llm_memory_import", "LLM memory import", f"```json\n{payload.memory_json.strip()}\n```")
    try:
        data = json.loads(payload.memory_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    people = db.scalars(select(Person).order_by(Person.id.asc())).all()
    rows = memory_to_extractions(data, people)
    for row in rows:
        db.add(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return ok({"created": len(rows), "ids": [row.id for row in rows], "source_document": source_document})


@router.get("/llm-prompt-template")
def get_llm_prompt_template():
    return ok({"template": LLM_PROMPT_TEMPLATE})


def chunk_text(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    chunks = []
    current = ""
    for paragraph in content.splitlines(keepends=True):
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(paragraph[index : index + max_chars] for index in range(0, len(paragraph), max_chars))
            continue
        if current and len(current) + len(paragraph) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current += paragraph
    if current:
        chunks.append(current)
    return chunks


def file_chunks_to_extractions(
    db: Session,
    chunks: list[str],
    source_file: str,
    target_type: str | None,
    target_id: int | None,
) -> list[Extraction]:
    settings = read_settings(db)
    model = settings.get("extraction_model", "anthropic/claude-haiku-4-5-20251001")
    people = db.scalars(select(Person).order_by(Person.importance.desc(), Person.name.asc())).all()
    relationships = db.scalars(select(Relationship).order_by(Relationship.id.asc())).all()
    rows: list[Extraction] = []
    for index, chunk in enumerate(chunks):
        output = LLMClient().complete_json(model, file_extraction_messages(chunk, source_file, index + 1, len(chunks), target_type, target_id))
        model_rows = _model_output_to_extractions(None, output, people, relationships) if output is not None else []
        if model_rows:
            for row in model_rows:
                tag_file_extraction(row, source_file, index + 1, len(chunks))
            rows.extend(model_rows)
        else:
            rows.append(note_extraction(chunk, source_file, index + 1, len(chunks), target_type, target_id))
    return rows


def file_extraction_messages(
    chunk: str,
    source_file: str,
    chunk_index: int,
    chunk_total: int,
    target_type: str | None,
    target_id: int | None,
) -> list[dict[str, str]]:
    target_hint = f"{target_type or 'self'}:{target_id}" if target_id is not None else (target_type or "self")
    prompt = (
        "你是用户的关系图谱抽取助手。只输出 JSON，无任何解释。\n"
        "从导入文件文本中识别人物、实体、事件、关系变化和用户自身画像更新。\n"
        "输出格式与聊天抽取相同：people/entities/events/relationships/self_updates。\n\n"
        f"# 文件\n{source_file}\n"
        f"# 分块\n{chunk_index}/{chunk_total}\n"
        f"# 目标提示\n{target_hint}\n\n"
        f"# 文本\n{chunk}"
    )
    return [{"role": "user", "content": prompt}]


def tag_file_extraction(row: Extraction, source_file: str, chunk_index: int, chunk_total: int) -> None:
    if row.kind == "event_new":
        row.payload = {
            **row.payload,
            "source": "file_import",
            "source_file": source_file,
            "source_chunk_index": chunk_index,
            "source_chunk_total": chunk_total,
        }
        row.payload.pop("source_session_id", None)


def note_extraction(
    chunk: str,
    source_file: str,
    chunk_index: int,
    chunk_total: int,
    target_type: str | None,
    target_id: int | None,
) -> Extraction:
    return Extraction(
        kind="note_new",
        payload={
            "target_type": target_type or "self",
            "target_id": target_id,
            "content": chunk,
            "source": "file_import",
            "source_file": source_file,
            "source_chunk_index": chunk_index,
            "source_chunk_total": chunk_total,
        },
        confidence=0.8,
        status="pending",
    )


def memory_to_extractions(data: dict[str, Any], existing_people: list[Person] | None = None) -> list[Extraction]:
    existing_people = existing_people or []
    rows: list[Extraction] = []
    for person in data.get("people") or []:
        profile_json = person.get("profile") or person.get("profile_json") or {}
        matched_person = match_imported_person(person, existing_people)
        if matched_person is not None:
            rows.append(
                Extraction(
                    kind="person_update",
                    payload={"person_id": matched_person.id, "profile_json": profile_json},
                    confidence=0.8,
                    status="pending",
                )
            )
            continue
        rows.append(
            Extraction(
                kind="person_new",
                payload={
                    "name": person.get("name"),
                    "aliases": person.get("aliases") or [],
                    "bio": person.get("bio"),
                    "profile_json": profile_json,
                },
                confidence=0.8,
                status="pending",
            )
        )
    for entity in data.get("entities") or []:
        rows.append(
            Extraction(
                kind="entity_new",
                payload={
                    "type": entity.get("type") or "org",
                    "name": entity.get("name"),
                    "bio": entity.get("bio"),
                    "profile_json": {"members": entity.get("members") or []},
                },
                confidence=0.8,
                status="pending",
            )
        )
    for event in data.get("events") or []:
        rows.append(
            Extraction(
                kind="event_new",
                payload={
                    "occurred_at": event.get("occurred_at"),
                    "title": event.get("title"),
                    "description": event.get("description"),
                    "participants": event_participant_payloads(event.get("participants") or [], existing_people),
                    "source": "llm_memory_import",
                },
                confidence=0.8,
                status="pending",
            )
        )
    if data.get("self"):
        rows.append(Extraction(kind="self_update", payload={"patches": data["self"]}, confidence=0.8, status="pending"))
    return rows


def event_participant_payloads(names: list[Any], existing_people: list[Person]) -> list[dict[str, Any]]:
    participants = []
    for name in names:
        matched_person = match_imported_person({"name": name}, existing_people)
        if matched_person is not None:
            participants.append({"type": "person", "id": matched_person.id})
        else:
            participants.append({"type": "name", "name": name})
    return participants


def match_imported_person(person: dict[str, Any], existing_people: list[Person]) -> Person | None:
    text = " ".join(_person_import_terms(person))
    if not text:
        return None
    for existing in existing_people:
        if person_matches_text(existing.name, existing.aliases, text):
            return existing
    return None


def _person_import_terms(person: dict[str, Any]) -> list[str]:
    terms = []
    if person.get("name"):
        terms.append(str(person["name"]))
    aliases = person.get("aliases") or []
    if isinstance(aliases, str):
        terms.append(aliases)
    elif isinstance(aliases, list):
        terms.extend(str(alias) for alias in aliases if alias)
    return terms
