from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.common import ok
from app.api.settings import read_settings
from app.db.session import get_db
from app.exporting import build_export_zip, export_obsidian

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/zip")
def export_zip(db: Session = Depends(get_db)):
    return Response(
        content=build_export_zip(db),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="dossier-export.zip"'},
    )


@router.post("/obsidian")
def export_to_obsidian(db: Session = Depends(get_db)):
    export_path = read_settings(db).get("obsidian_export_path")
    if not export_path:
        raise HTTPException(status_code=400, detail="obsidian_export_path not configured")
    result = export_obsidian(db, Path(str(export_path)))
    return ok(result)
