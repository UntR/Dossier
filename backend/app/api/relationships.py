from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, missing, model_dict, ok
from app.db.models import Relationship
from app.db.session import get_db
from app.schemas.phase2 import RelationshipCreate, RelationshipUpdate

router = APIRouter(prefix="/api/relationships", tags=["relationships"])

RELATIONSHIP_FIELDS = {
    "from_type",
    "from_id",
    "to_type",
    "to_id",
    "relation_type",
    "role",
    "strength",
    "status",
    "notes",
    "started_at",
    "ended_at",
}
DATE_FIELDS = {"started_at", "ended_at"}


def apply_endpoint_filter(stmt, value: str | None, side: str):
    if not value:
        return stmt
    type_value, _, id_value = value.partition(":")
    if side == "from":
        stmt = stmt.where(Relationship.from_type == type_value)
        if id_value:
            stmt = stmt.where(Relationship.from_id == int(id_value))
    else:
        stmt = stmt.where(Relationship.to_type == type_value)
        if id_value:
            stmt = stmt.where(Relationship.to_id == int(id_value))
    return stmt


@router.get("")
def list_relationships(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Relationship)
    stmt = apply_endpoint_filter(stmt, from_, "from")
    stmt = apply_endpoint_filter(stmt, to, "to")
    items = db.scalars(stmt.order_by(Relationship.id.asc())).all()
    return ok({"items": [model_dict(item) for item in items]})


@router.post("")
def create_relationship(payload: RelationshipCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    relationship = apply_fields(
        Relationship(
            from_type=data["from_type"],
            to_type=data["to_type"],
            to_id=data["to_id"],
            relation_type=data["relation_type"],
        ),
        data,
        RELATIONSHIP_FIELDS,
        DATE_FIELDS,
    )
    return ok(commit_model(db, relationship))


@router.get("/{relationship_id}")
def get_relationship(relationship_id: int, db: Session = Depends(get_db)):
    relationship = db.get(Relationship, relationship_id)
    if relationship is None:
        missing("relationship")
    return ok(model_dict(relationship))


@router.patch("/{relationship_id}")
def update_relationship(relationship_id: int, payload: RelationshipUpdate, db: Session = Depends(get_db)):
    relationship = db.get(Relationship, relationship_id)
    if relationship is None:
        missing("relationship")
    apply_fields(relationship, payload.model_dump(exclude_unset=True), RELATIONSHIP_FIELDS, DATE_FIELDS)
    return ok(commit_model(db, relationship))


@router.delete("/{relationship_id}")
def delete_relationship(relationship_id: int, db: Session = Depends(get_db)):
    relationship = db.get(Relationship, relationship_id)
    if relationship is None:
        missing("relationship")
    db.delete(relationship)
    db.commit()
    return ok({"id": relationship_id})
