from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import ok
from app.api.self_ import get_or_create_self
from app.db.models import Event, LifeStage, Person, PersonStage, Relationship
from app.db.session import get_db

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("")
def get_timeline(stage_id: int | None = None, relation_type: str | None = None, db: Session = Depends(get_db)):
    profile = get_or_create_self(db)
    allowed_person_ids = _person_ids_for_relation(db, relation_type)
    stages = db.scalars(_stage_query(stage_id)).all()
    stage_items = []
    for stage in stages:
        item = stage_payload(db, stage, allowed_person_ids)
        if item["people"] or not relation_type:
            stage_items.append(item)
    return ok({"self": {"name": profile.name}, "stages": stage_items})


def stage_payload(db: Session, stage: LifeStage, allowed_person_ids: set[int] | None) -> dict:
    assignments = db.scalars(select(PersonStage).where(PersonStage.stage_id == stage.id).order_by(PersonStage.started_at.asc())).all()
    people = []
    for assignment in assignments:
        if allowed_person_ids is not None and assignment.person_id not in allowed_person_ids:
            continue
        person = db.get(Person, assignment.person_id)
        if person is None:
            continue
        people.append(
            {
                "person_id": person.id,
                "name": person.name,
                "role_in_stage": assignment.role_in_stage,
                "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
                "ended_at": assignment.ended_at.isoformat() if assignment.ended_at else None,
            }
        )
    person_ids = {person["person_id"] for person in people}
    return {
        "id": stage.id,
        "name": stage.name,
        "kind": stage.kind,
        "started_at": stage.started_at.isoformat() if stage.started_at else None,
        "ended_at": stage.ended_at.isoformat() if stage.ended_at else None,
        "people": people,
        "events": _stage_events(db, stage, person_ids),
    }


def _stage_query(stage_id: int | None):
    stmt = select(LifeStage)
    if stage_id is not None:
        stmt = stmt.where(LifeStage.id == stage_id)
    return stmt.order_by(LifeStage.sort_order.asc(), LifeStage.started_at.asc())


def _person_ids_for_relation(db: Session, relation_type: str | None) -> set[int] | None:
    if not relation_type:
        return None
    rows = db.scalars(select(Relationship).where(Relationship.relation_type == relation_type)).all()
    ids = set()
    for row in rows:
        if row.from_type == "person" and row.from_id is not None:
            ids.add(row.from_id)
        if row.to_type == "person":
            ids.add(row.to_id)
    return ids


def _stage_events(db: Session, stage: LifeStage, person_ids: set[int]) -> list[dict]:
    if not person_ids:
        return []
    events = []
    for event in db.scalars(select(Event).order_by(Event.occurred_at.asc())).all():
        if not event.occurred_at or not _date_in_stage(event.occurred_at, stage):
            continue
        if not any(participant.get("type") == "person" and participant.get("id") in person_ids for participant in event.participants or []):
            continue
        events.append({"id": event.id, "title": event.title, "occurred_at": event.occurred_at.isoformat()})
    return events


def _date_in_stage(value: date, stage: LifeStage) -> bool:
    if stage.started_at and value < stage.started_at:
        return False
    if stage.ended_at and value > stage.ended_at:
        return False
    return True
