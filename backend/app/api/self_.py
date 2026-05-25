from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import apply_fields, commit_model, model_dict, ok
from app.db.models import SelfProfile
from app.db.session import get_db
from app.schemas.phase2 import SelfProfileUpdate

router = APIRouter(prefix="/api/self", tags=["self"])

SELF_FIELDS = {"name", "bio", "communication_style", "sensitivities", "goals", "profile_json"}


def get_or_create_self(db: Session) -> SelfProfile:
    profile = db.get(SelfProfile, 1)
    if profile is None:
        profile = SelfProfile(id=1, name="我", sensitivities=[], goals=[], profile_json={})
        db.add(profile)
        try:
            db.commit()
            db.refresh(profile)
        except IntegrityError:
            db.rollback()
            profile = db.get(SelfProfile, 1)
    return profile


@router.get("")
def get_self(db: Session = Depends(get_db)):
    return ok(model_dict(get_or_create_self(db)))


@router.patch("")
def update_self(payload: SelfProfileUpdate, db: Session = Depends(get_db)):
    profile = get_or_create_self(db)
    apply_fields(profile, payload.model_dump(exclude_unset=True), SELF_FIELDS)
    return ok(commit_model(db, profile))
