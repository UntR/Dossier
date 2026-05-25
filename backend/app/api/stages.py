from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, missing, model_dict, ok
from app.db.models import LifeStage
from app.db.session import get_db
from app.schemas.phase2 import LifeStageCreate, LifeStageUpdate

router = APIRouter(prefix="/api/stages", tags=["stages"])

STAGE_FIELDS = {"name", "kind", "location", "started_at", "ended_at", "notes", "sort_order"}
DATE_FIELDS = {"started_at", "ended_at"}


@router.get("")
def list_stages(db: Session = Depends(get_db)):
    items = db.scalars(select(LifeStage).order_by(LifeStage.sort_order.asc(), LifeStage.started_at.asc())).all()
    return ok({"items": [model_dict(item) for item in items]})


@router.post("")
def create_stage(payload: LifeStageCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    stage = apply_fields(LifeStage(name=data["name"]), data, STAGE_FIELDS, DATE_FIELDS)
    return ok(commit_model(db, stage))


@router.patch("/{stage_id}")
def update_stage(stage_id: int, payload: LifeStageUpdate, db: Session = Depends(get_db)):
    stage = db.get(LifeStage, stage_id)
    if stage is None:
        missing("stage")
    apply_fields(stage, payload.model_dump(exclude_unset=True), STAGE_FIELDS, DATE_FIELDS)
    return ok(commit_model(db, stage))


@router.delete("/{stage_id}")
def delete_stage(stage_id: int, db: Session = Depends(get_db)):
    stage = db.get(LifeStage, stage_id)
    if stage is None:
        missing("stage")
    db.delete(stage)
    db.commit()
    return ok({"id": stage_id})
