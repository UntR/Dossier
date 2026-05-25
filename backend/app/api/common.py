from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def missing(resource: str) -> None:
    raise HTTPException(status_code=404, detail=f"{resource} not found")


def serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def model_dict(model: Any) -> dict[str, Any]:
    return {
        column.name: serialize(getattr(model, column.name))
        for column in model.__table__.columns
    }


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def text_matches(value: Any, query: str) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(text_matches(item, query) for item in value)
    if isinstance(value, dict):
        return any(text_matches(item, query) for item in value.values())
    return query in str(value)


def apply_fields(model: Any, payload: dict[str, Any], allowed: set[str], date_fields: set[str] | None = None) -> Any:
    date_fields = date_fields or set()
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key in date_fields:
            value = parse_date(value)
        setattr(model, key, value)
    return model


def commit_model(db: Session, model: Any) -> dict[str, Any]:
    db.add(model)
    db.commit()
    db.refresh(model)
    return model_dict(model)


async def save_upload(file: UploadFile, upload_root: str) -> str:
    data = await file.read()
    digest = hashlib.sha1(data).hexdigest()
    suffix = Path(file.filename or "").suffix.lower() or ".bin"
    photos_dir = Path(upload_root) / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    target = photos_dir / f"{digest}{suffix}"
    target.write_bytes(data)
    return f"/api/files/photos/{target.name}"
