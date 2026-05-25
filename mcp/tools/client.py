from __future__ import annotations

import os
from typing import Any

import httpx


def api_url() -> str:
    return os.getenv("DOSSIER_API_URL", "http://127.0.0.1:8000").rstrip("/")


async def request_json(method: str, path: str, **kwargs: Any) -> Any:
    async with httpx.AsyncClient(base_url=api_url(), timeout=30.0) as client:
        response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    body = response.json()
    if isinstance(body, dict) and body.get("ok") is True:
        return body.get("data")
    return body
