from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.common import parse_date
from app.db.models import Entity, Event, Extraction, Note, Person, Relationship, SelfProfile


def apply_extraction(db: Session, extraction: Extraction) -> int | None:
    payload = extraction.payload or {}
    target_id = None
    if extraction.kind == "event_new":
        target_id = _apply_event(db, extraction, payload)
    elif extraction.kind == "relationship_new":
        target_id = _apply_relationship(db, payload)
    elif extraction.kind == "relationship_update":
        target_id = _apply_relationship_update(db, payload)
    elif extraction.kind == "self_update":
        target_id = _apply_self_update(db, payload)
    elif extraction.kind == "person_new":
        target_id = _apply_person(db, payload)
    elif extraction.kind == "person_update":
        target_id = _apply_person_update(db, payload)
    elif extraction.kind == "entity_new":
        target_id = _apply_entity(db, payload)
    elif extraction.kind == "note_new":
        target_id = _apply_note(db, payload)
    extraction.target_id = target_id
    extraction.applied_at = datetime.now(UTC).replace(tzinfo=None)
    return target_id


def undo_extraction(db: Session, extraction: Extraction) -> None:
    if extraction.target_id is None:
        raise HTTPException(status_code=409, detail="extraction has no applied target")
    target = _undo_target(db, extraction.kind, extraction.target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="applied target not found")
    db.delete(target)
    extraction.status = "rejected"
    extraction.applied_at = datetime.now(UTC).replace(tzinfo=None)


def _undo_target(db: Session, kind: str, target_id: int) -> Any | None:
    models = {
        "event_new": Event,
        "relationship_new": Relationship,
        "person_new": Person,
        "entity_new": Entity,
        "note_new": Note,
    }
    model = models.get(kind)
    if model is None:
        raise HTTPException(status_code=409, detail=f"{kind} cannot be undone without before state")
    return db.get(model, target_id)


def _apply_event(db: Session, extraction: Extraction, payload: dict[str, Any]) -> int:
    event = Event(
        occurred_at=parse_date(payload.get("occurred_at")),
        title=payload["title"],
        description=payload.get("description"),
        participants=payload.get("participants"),
        source=payload.get("source", "extraction"),
        source_session_id=payload.get("source_session_id", extraction.session_id),
        importance=payload.get("importance", 0),
    )
    db.add(event)
    db.flush()
    return event.id


def _apply_relationship(db: Session, payload: dict[str, Any]) -> int:
    relationship = Relationship(
        from_type=payload["from_type"],
        from_id=payload.get("from_id"),
        to_type=payload["to_type"],
        to_id=payload["to_id"],
        relation_type=payload["relation_type"],
        role=payload.get("role"),
        strength=payload.get("strength"),
        status=payload.get("status"),
        notes=payload.get("notes"),
        started_at=parse_date(payload.get("started_at")),
        ended_at=parse_date(payload.get("ended_at")),
    )
    db.add(relationship)
    db.flush()
    return relationship.id


def _apply_relationship_update(db: Session, payload: dict[str, Any]) -> int:
    relationship = db.get(Relationship, payload["relationship_id"])
    if relationship is None:
        raise HTTPException(status_code=404, detail="relationship not found")
    for key in ("relation_type", "role", "strength", "status", "notes"):
        if key in payload:
            setattr(relationship, key, payload[key])
    if "started_at" in payload:
        relationship.started_at = parse_date(payload["started_at"])
    if "ended_at" in payload:
        relationship.ended_at = parse_date(payload["ended_at"])
    db.flush()
    return relationship.id


def _apply_self_update(db: Session, payload: dict[str, Any]) -> int:
    profile = db.get(SelfProfile, 1)
    if profile is None:
        profile = SelfProfile(id=1, name="我")
        db.add(profile)
        db.flush()
    for key, value in (payload.get("patches") or {}).items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    return profile.id


def _apply_person(db: Session, payload: dict[str, Any]) -> int:
    person = Person(
        name=payload["name"],
        aliases=payload.get("aliases"),
        bio=payload.get("bio"),
        profile_json=payload.get("profile_json"),
        importance=payload.get("importance", 0),
    )
    db.add(person)
    db.flush()
    return person.id


def _apply_person_update(db: Session, payload: dict[str, Any]) -> int:
    person = db.get(Person, payload["person_id"])
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    person.profile_json = payload["profile_json"]
    db.flush()
    return person.id


def _apply_entity(db: Session, payload: dict[str, Any]) -> int:
    entity = Entity(
        type=payload.get("type", "org"),
        name=payload["name"],
        bio=payload.get("bio"),
        profile_json=payload.get("profile_json"),
    )
    db.add(entity)
    db.flush()
    return entity.id


def _apply_note(db: Session, payload: dict[str, Any]) -> int:
    note = Note(
        target_type=payload["target_type"],
        target_id=payload.get("target_id"),
        content=payload["content"],
        source=payload.get("source", "extraction"),
        source_file=payload.get("source_file"),
    )
    db.add(note)
    db.flush()
    return note.id
