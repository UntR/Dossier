from __future__ import annotations

from typing import Any

import anyio

from tools.client import request_json


async def interpret_message(message: str, from_hint: str | None = None, context_hint: str | None = None) -> dict[str, Any]:
    return await request_json(
        "POST",
        "/api/mcp/interpret",
        json={"message": message, "from_hint": from_hint, "context_hint": context_hint},
    )


async def prepare_conversation(
    with_person: str,
    desired_outcome: str | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    return await request_json(
        "POST",
        "/api/mcp/prepare",
        json={"with_person": with_person, "desired_outcome": desired_outcome, "scenario": scenario},
    )


async def stale_contacts(days: int = 30) -> list[dict[str, Any]]:
    data = await request_json("GET", "/api/mcp/stale-contacts", params={"days": days})
    return data.get("items", data)


async def recent_changes(person: str | None = None, days: int = 7) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"days": days}
    if person:
        params["person"] = person
    data = await request_json("GET", "/api/mcp/recent-changes", params=params)
    return data.get("items", data)
