from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, missing, model_dict, ok, save_upload, text_matches
from app.config import get_settings
from app.db.models import EntityMember, Event, LifeStage, Note, Person, PersonStage, Relationship
from app.db.session import get_db
from app.schemas.phase2 import PersonCreate, PersonMergeRequest, PersonStageCreate, PersonUpdate

router = APIRouter(prefix="/api/people", tags=["people"])

PERSON_FIELDS = {"name", "aliases", "bio", "profile_json", "photo_path", "importance"}


@router.get("")
def list_people(q: str | None = None, sort: str = "name", limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(Person)
    if q:
        items = [
            item
            for item in db.scalars(stmt.order_by(Person.name.asc())).all()
            if text_matches(item.name, q) or text_matches(item.bio, q) or text_matches(item.aliases, q)
        ]
        return ok({"items": [model_dict(item) for item in items[offset : offset + limit]], "limit": limit, "offset": offset})
    if sort == "importance":
        stmt = stmt.order_by(Person.importance.desc(), Person.name.asc())
    else:
        stmt = stmt.order_by(Person.name.asc())
    items = db.scalars(stmt.offset(offset).limit(limit)).all()
    return ok({"items": [model_dict(item) for item in items], "limit": limit, "offset": offset})


@router.post("")
def create_person(payload: PersonCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    person = apply_fields(Person(name=data["name"]), data, PERSON_FIELDS)
    return ok(commit_model(db, person))


@router.get("/{person_id}")
def get_person(person_id: int, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        missing("person")
    relationships = db.scalars(
        select(Relationship).where(
            or_(
                (Relationship.from_type == "person") & (Relationship.from_id == person_id),
                (Relationship.to_type == "person") & (Relationship.to_id == person_id),
            )
        )
    ).all()
    events = [
        event
        for event in db.scalars(select(Event).order_by(Event.occurred_at.desc())).all()
        if any(participant.get("type") == "person" and participant.get("id") == person_id for participant in event.participants or [])
    ]
    notes = db.scalars(select(Note).where(Note.target_type == "person", Note.target_id == person_id)).all()
    stages = db.scalars(select(PersonStage).where(PersonStage.person_id == person_id)).all()
    return ok(
        {
            "person": model_dict(person),
            "relationships": [model_dict(item) for item in relationships],
            "events": [model_dict(item) for item in events],
            "notes": [model_dict(item) for item in notes],
            "stages": [
                {**model_dict(item), "stage": model_dict(db.get(LifeStage, item.stage_id))}
                for item in stages
            ],
        }
    )


@router.patch("/{person_id}")
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        missing("person")
    apply_fields(person, payload.model_dump(exclude_unset=True), PERSON_FIELDS)
    return ok(commit_model(db, person))


@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        missing("person")
    db.delete(person)
    db.commit()
    return ok({"id": person_id})


@router.post("/{person_id}/merge")
def merge_person(person_id: int, payload: PersonMergeRequest, db: Session = Depends(get_db)):
    target_id = payload.target_person_id
    source = db.get(Person, person_id)
    target = db.get(Person, target_id)
    if source is None or target is None:
        missing("person")
    if person_id == target_id:
        return ok({"source_id": person_id, "target_id": target_id})

    db.execute(update(Relationship).where(Relationship.from_type == "person", Relationship.from_id == person_id).values(from_id=target_id))
    db.execute(update(Relationship).where(Relationship.to_type == "person", Relationship.to_id == person_id).values(to_id=target_id))
    db.execute(update(Note).where(Note.target_type == "person", Note.target_id == person_id).values(target_id=target_id))

    for membership in db.scalars(select(EntityMember).where(EntityMember.person_id == person_id)).all():
        existing = db.scalar(
            select(EntityMember).where(EntityMember.entity_id == membership.entity_id, EntityMember.person_id == target_id)
        )
        if existing:
            db.delete(membership)
        else:
            membership.person_id = target_id

    for stage in db.scalars(select(PersonStage).where(PersonStage.person_id == person_id)).all():
        existing = db.scalar(select(PersonStage).where(PersonStage.stage_id == stage.stage_id, PersonStage.person_id == target_id))
        if existing:
            db.delete(stage)
        else:
            stage.person_id = target_id

    for event in db.scalars(select(Event)).all():
        changed = False
        participants = []
        for participant in event.participants or []:
            if participant.get("type") == "person" and participant.get("id") == person_id:
                participant = {**participant, "id": target_id}
                changed = True
            participants.append(participant)
        if changed:
            event.participants = participants

    db.delete(source)
    db.commit()
    return ok({"source_id": person_id, "target_id": target_id})


@router.post("/{person_id}/stages")
def add_person_stage(person_id: int, payload: PersonStageCreate, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    stage = db.get(LifeStage, payload.stage_id)
    if person is None:
        missing("person")
    if stage is None:
        missing("stage")
    existing = db.scalar(select(PersonStage).where(PersonStage.person_id == person_id, PersonStage.stage_id == payload.stage_id))
    if existing:
        existing.role_in_stage = payload.role_in_stage
        existing.started_at = payload.started_at
        existing.ended_at = payload.ended_at
        return ok(commit_model(db, existing))
    assignment = PersonStage(
        person_id=person_id,
        stage_id=payload.stage_id,
        role_in_stage=payload.role_in_stage,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
    )
    return ok(commit_model(db, assignment))


@router.delete("/{person_id}/stages/{stage_id}")
def remove_person_stage(person_id: int, stage_id: int, db: Session = Depends(get_db)):
    assignment = db.scalar(select(PersonStage).where(PersonStage.person_id == person_id, PersonStage.stage_id == stage_id))
    if assignment is None:
        missing("person stage")
    db.delete(assignment)
    db.commit()
    return ok({"person_id": person_id, "stage_id": stage_id})


@router.post("/{person_id}/photo")
async def upload_photo(person_id: int, file: UploadFile, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        missing("person")
    photo_path = await save_upload(file, get_settings().upload_dir)
    person.photo_path = photo_path
    db.commit()
    db.refresh(person)
    return ok({"id": person_id, "photo_path": photo_path})
