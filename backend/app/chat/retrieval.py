from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.common import model_dict
from app.db.models import Entity, Event, Person, Relationship, SelfProfile
from app.matching import person_matches_text

CONTEXT_CACHE_SIZE = 128
ContextCacheKey = tuple[str, int, tuple[int, ...]]
_context_cache: OrderedDict[ContextCacheKey, dict[str, Any]] = OrderedDict()


def retrieve_context(db: Session, message: str, session_id: int | None = None) -> dict:
    people = [
        person
        for person in db.scalars(select(Person).order_by(Person.importance.desc(), Person.name.asc())).all()
        if _person_matches_message(person, message)
    ][:5]
    person_ids = {person.id for person in people}
    cache_key = _context_cache_key(db, session_id, person_ids)
    if cache_key in _context_cache:
        _context_cache.move_to_end(cache_key)
        return deepcopy(_context_cache[cache_key])

    self_profile = db.get(SelfProfile, 1)
    relationships = []
    if person_ids:
        relationships = db.scalars(
            select(Relationship).where(
                or_(
                    (Relationship.from_type == "person") & (Relationship.from_id.in_(person_ids)),
                    (Relationship.to_type == "person") & (Relationship.to_id.in_(person_ids)),
                )
            )
        ).all()
    events = [
        event
        for event in db.scalars(select(Event).order_by(Event.occurred_at.desc()).limit(50)).all()
        if any(participant.get("type") == "person" and participant.get("id") in person_ids for participant in event.participants or [])
    ][:10]
    entities = db.scalars(select(Entity).limit(5)).all() if people else []
    context = {
        "self": model_dict(self_profile) if self_profile else None,
        "people": [model_dict(person) for person in people],
        "relationships": [model_dict(relationship) for relationship in relationships],
        "events": [model_dict(event) for event in events],
        "entities": [model_dict(entity) for entity in entities],
    }
    if cache_key is not None:
        _context_cache[cache_key] = deepcopy(context)
        _context_cache.move_to_end(cache_key)
        while len(_context_cache) > CONTEXT_CACHE_SIZE:
            _context_cache.popitem(last=False)
    return context


def _person_matches_message(person: Person, message: str) -> bool:
    return person_matches_text(person.name, person.aliases, message)


def _context_cache_key(db: Session, session_id: int | None, person_ids: set[int]) -> ContextCacheKey | None:
    if session_id is None:
        return None
    return (str(db.get_bind().url), session_id, tuple(sorted(person_ids)))
