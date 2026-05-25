from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import missing, model_dict, ok
from app.api.settings import read_settings
from app.db.models import Extraction
from app.db.session import get_db
from app.extraction.applier import apply_extraction, undo_extraction
from app.llm.client import LLMClient

router = APIRouter(prefix="/api/extractions", tags=["extractions"])


class BulkExtractionAction(BaseModel):
    accept: list[int] = []
    reject: list[int] = []


class ExtractionUpdate(BaseModel):
    payload: dict[str, Any] | None = None
    confidence: float | None = None


class ExtractionRepair(BaseModel):
    error: str | None = None


@router.get("")
def list_extractions(status: str | None = "pending", db: Session = Depends(get_db)):
    stmt = select(Extraction)
    if status:
        stmt = stmt.where(Extraction.status == status)
    items = db.scalars(stmt.order_by(Extraction.created_at.desc(), Extraction.id.desc())).all()
    return ok({"items": [model_dict(item) for item in items]})


@router.patch("/{extraction_id}")
def update_extraction(extraction_id: int, payload: ExtractionUpdate, db: Session = Depends(get_db)):
    extraction = _get_pending(db, extraction_id)
    if payload.payload is not None:
        extraction.payload = payload.payload
    if payload.confidence is not None:
        extraction.confidence = payload.confidence
    db.commit()
    db.refresh(extraction)
    return ok(model_dict(extraction))


@router.post("/{extraction_id}/repair")
def repair_extraction(extraction_id: int, payload: ExtractionRepair, db: Session = Depends(get_db)):
    extraction = _get_pending(db, extraction_id)
    repaired_payload = _repair_payload_with_model(db, extraction, payload.error)
    extraction.payload = repaired_payload
    db.commit()
    db.refresh(extraction)
    return ok(model_dict(extraction))


@router.post("/{extraction_id}/accept")
def accept_extraction(extraction_id: int, db: Session = Depends(get_db)):
    extraction = _get_pending(db, extraction_id)
    apply_extraction(db, extraction)
    extraction.status = "accepted"
    db.commit()
    db.refresh(extraction)
    return ok(model_dict(extraction))


@router.post("/{extraction_id}/reject")
def reject_extraction(extraction_id: int, db: Session = Depends(get_db)):
    extraction = _get_pending(db, extraction_id)
    extraction.status = "rejected"
    extraction.applied_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(extraction)
    return ok(model_dict(extraction))


@router.post("/{extraction_id}/undo")
def undo_applied_extraction(extraction_id: int, db: Session = Depends(get_db)):
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        missing("extraction")
    if extraction.status not in {"accepted", "auto_applied"}:
        missing("applied extraction")
    undo_extraction(db, extraction)
    db.commit()
    db.refresh(extraction)
    return ok(model_dict(extraction))


@router.post("/bulk")
def bulk_action(payload: BulkExtractionAction, db: Session = Depends(get_db)):
    accepted = []
    rejected = []
    for extraction_id in payload.accept:
        extraction = _get_pending(db, extraction_id)
        apply_extraction(db, extraction)
        extraction.status = "accepted"
        accepted.append(extraction_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    for extraction_id in payload.reject:
        extraction = _get_pending(db, extraction_id)
        extraction.status = "rejected"
        extraction.applied_at = now
        rejected.append(extraction_id)
    db.commit()
    return ok({"accepted": accepted, "rejected": rejected})


def _repair_payload_with_model(db: Session, extraction: Extraction, error: str | None) -> dict[str, Any]:
    settings = read_settings(db)
    model = settings.get("extraction_model", "anthropic/claude-haiku-4-5-20251001")
    output = LLMClient().complete_json(model, _repair_messages(extraction, error))
    repaired_payload = _repaired_payload(output)
    if repaired_payload is None:
        raise HTTPException(status_code=502, detail="model repair unavailable")
    return repaired_payload


def _repair_messages(extraction: Extraction, error: str | None) -> list[dict[str, str]]:
    prompt = (
        "你是 Dossier 抽取 payload 的格式修复器。只输出 JSON，无任何解释。\n"
        "输出格式必须是 {\"payload\": {...}}。\n"
        "不要改写事实内容，不要新增原 payload 没有的信息。\n"
        "无法确定的日期字段必须用 null；日期字段只能是 YYYY-MM-DD 或 null。\n\n"
        "# 目标 payload 约束\n"
        "- event_new.occurred_at: YYYY-MM-DD 或 null\n"
        "- relationship_new.started_at / ended_at: YYYY-MM-DD 或 null\n"
        "- relationship_update.started_at / ended_at: YYYY-MM-DD 或 null\n"
        "- 其他字段保持原语义和原结构，只修正导致落库失败的格式。\n\n"
        f"# kind\n{extraction.kind}\n\n"
        f"# 失败原因\n{error or '未提供'}\n\n"
        f"# 当前 payload\n{json.dumps(extraction.payload, ensure_ascii=False, indent=2)}"
    )
    return [{"role": "user", "content": prompt}]


def _repaired_payload(output: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(output, dict):
        return None
    payload = output.get("payload", output)
    return payload if isinstance(payload, dict) else None


def _get_pending(db: Session, extraction_id: int) -> Extraction:
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        missing("extraction")
    if extraction.status != "pending":
        missing("pending extraction")
    return extraction
