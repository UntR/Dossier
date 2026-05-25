from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, missing, model_dict, ok, parse_date
from app.db.models import Entity, EntityMember, Person
from app.db.session import get_db
from app.schemas.phase2 import EntityCreate, EntityMemberCreate, EntityUpdate

router = APIRouter(prefix="/api/entities", tags=["entities"])

ENTITY_FIELDS = {"type", "name", "bio", "profile_json"}


@router.get("")
def list_entities(q: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(Entity).order_by(Entity.name.asc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Entity.name.like(like), Entity.bio.like(like), cast(Entity.profile_json, String).like(like)))
    items = db.scalars(stmt.offset(offset).limit(limit)).all()
    return ok({"items": [model_dict(item) for item in items], "limit": limit, "offset": offset})


@router.post("")
def create_entity(payload: EntityCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    entity = apply_fields(Entity(type=data["type"], name=data["name"]), data, ENTITY_FIELDS)
    return ok(commit_model(db, entity))


@router.get("/{entity_id}")
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        missing("entity")
    members = db.scalars(select(EntityMember).where(EntityMember.entity_id == entity_id)).all()
    return ok(
        {
            "entity": model_dict(entity),
            "members": [
                {**model_dict(member), "person": model_dict(db.get(Person, member.person_id))}
                for member in members
            ],
        }
    )


@router.patch("/{entity_id}")
def update_entity(entity_id: int, payload: EntityUpdate, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        missing("entity")
    apply_fields(entity, payload.model_dump(exclude_unset=True), ENTITY_FIELDS)
    return ok(commit_model(db, entity))


@router.delete("/{entity_id}")
def delete_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        missing("entity")
    db.delete(entity)
    db.commit()
    return ok({"id": entity_id})


@router.post("/{entity_id}/members")
def add_member(entity_id: int, payload: EntityMemberCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if db.get(Entity, entity_id) is None:
        missing("entity")
    if db.get(Person, data["person_id"]) is None:
        missing("person")
    member = EntityMember(
        entity_id=entity_id,
        person_id=data["person_id"],
        role=data.get("role"),
        started_at=parse_date(data.get("started_at")),
        ended_at=parse_date(data.get("ended_at")),
    )
    return ok(commit_model(db, member))


@router.delete("/{entity_id}/members/{person_id}")
def remove_member(entity_id: int, person_id: int, db: Session = Depends(get_db)):
    member = db.scalar(select(EntityMember).where(EntityMember.entity_id == entity_id, EntityMember.person_id == person_id))
    if member is None:
        missing("entity member")
    db.delete(member)
    db.commit()
    return ok({"entity_id": entity_id, "person_id": person_id})
