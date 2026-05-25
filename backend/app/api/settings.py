from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import ok
from app.db.models import AppSetting
from app.db.session import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDER_MODELS = {
    "anthropic": ["anthropic/claude-sonnet-4-6", "anthropic/claude-haiku-4-5-20251001"],
    "openai": ["openai/gpt-4.1", "openai/gpt-4.1-mini"],
    "google": ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"],
    "ollama": ["ollama/qwen2.5", "ollama/llama3.1"],
}


def read_settings(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(AppSetting).order_by(AppSetting.key.asc())).all()
    return {row.key: row.value for row in rows}


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return ok(read_settings(db))


@router.patch("")
def patch_settings(payload: dict[str, Any], db: Session = Depends(get_db)):
    for key, value in payload.items():
        row = db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
    db.commit()
    return ok(read_settings(db))


@router.get("/models")
def list_models():
    ollama_configured, ollama_models = ollama_provider_models()
    providers = [
        {
            "provider": "anthropic",
            "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "models": PROVIDER_MODELS["anthropic"],
        },
        {
            "provider": "openai",
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "models": PROVIDER_MODELS["openai"],
        },
        {
            "provider": "google",
            "configured": bool(os.getenv("GOOGLE_API_KEY")),
            "models": PROVIDER_MODELS["google"],
        },
        {
            "provider": "ollama",
            "configured": ollama_configured,
            "models": ollama_models,
        },
    ]
    return ok({"providers": providers})


def ollama_provider_models() -> tuple[bool, list[str]]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    if not base_url:
        return False, PROVIDER_MODELS["ollama"]
    try:
        with httpx.Client(base_url=base_url, timeout=1.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = [
                f"ollama/{model['name']}"
                for model in response.json().get("models", [])
                if model.get("name")
            ]
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return True, PROVIDER_MODELS["ollama"]
    return True, models or PROVIDER_MODELS["ollama"]
