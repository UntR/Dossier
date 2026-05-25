from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, missing, model_dict, ok
from app.db.models import Event
from app.db.session import get_db
from app.schemas.phase2 import EventCreate, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])

EVENT_FIELDS = {"occurred_at", "title", "description", "participants", "source", "source_session_id", "importance"}
DATE_FIELDS = {"occurred_at"}


@router.get("")
def list_events(person_id: int | None = None, since: str | None = None, until: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Event).order_by(Event.occurred_at.desc())
    items = db.scalars(stmt).all()
    if person_id is not None:
        items = [
            item
            for item in items
            if any(participant.get("type") == "person" and participant.get("id") == person_id for participant in item.participants or [])
        ]
    if since:
        items = [item for item in items if item.occurred_at and item.occurred_at.isoformat() >= since]
    if until:
        items = [item for item in items if item.occurred_at and item.occurred_at.isoformat() <= until]
    return ok({"items": [model_dict(item) for item in items]})


@router.post("")
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    event = apply_fields(Event(title=data["title"]), data, EVENT_FIELDS, DATE_FIELDS)
    return ok(commit_model(db, event))


@router.patch("/{event_id}")
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        missing("event")
    apply_fields(event, payload.model_dump(exclude_unset=True), EVENT_FIELDS, DATE_FIELDS)
    return ok(commit_model(db, event))


@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        missing("event")
    db.delete(event)
    db.commit()
    return ok({"id": event_id})
