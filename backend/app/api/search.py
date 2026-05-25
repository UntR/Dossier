from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.common import model_dict, ok, text_matches
from app.db.models import Entity, Event, Note, Person
from app.db.session import get_db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str, type: str | None = None, db: Session = Depends(get_db)):
    like = f"%{q}%"
    data = {"people": [], "entities": [], "notes": [], "events": []}
    if type in (None, "people", "person"):
        people = [
            item
            for item in db.scalars(select(Person).order_by(Person.name.asc())).all()
            if text_matches(item.name, q) or text_matches(item.bio, q) or text_matches(item.aliases, q) or text_matches(item.profile_json, q)
        ][:20]
        data["people"] = [model_dict(item) for item in people]
    if type in (None, "entities", "entity"):
        entities = [
            item
            for item in db.scalars(select(Entity).order_by(Entity.name.asc())).all()
            if text_matches(item.name, q) or text_matches(item.bio, q) or text_matches(item.profile_json, q)
        ][:20]
        data["entities"] = [model_dict(item) for item in entities]
    if type in (None, "notes", "note"):
        notes = db.scalars(select(Note).where(Note.content.like(like)).limit(20)).all()
        data["notes"] = [model_dict(item) for item in notes]
    if type in (None, "events", "event"):
        events = db.scalars(select(Event).where(or_(Event.title.like(like), Event.description.like(like))).limit(20)).all()
        data["events"] = [model_dict(item) for item in events]
    return ok(data)
