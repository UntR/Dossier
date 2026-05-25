from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/photos/{filename}")
def get_photo(filename: str):
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="photo not found")
    path = Path(get_settings().upload_dir) / "photos" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path)
