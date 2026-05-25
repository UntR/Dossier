from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import anyio

from tools.client import request_json


async def get_person(name_or_id: str) -> dict[str, Any] | None:
    if name_or_id.isdigit():
        data = await request_json("GET", f"/api/people/{name_or_id}")
        return data.get("person", data)
    people = await search_people(name_or_id, 1)
    if not people:
        return None
    data = await request_json("GET", f"/api/people/{people[0]['id']}")
    return data.get("person", data)


async def search_people(query: str, limit: int = 10) -> list[dict[str, Any]]:
    data = await request_json("GET", "/api/search", params={"q": query, "type": "people"})
    return (data.get("people") or [])[:limit]


async def get_relationship(person_a: str, person_b: str | None = None) -> list[dict[str, Any]]:
    first = await get_person(person_a)
    if not first:
        return []
    if person_b is None:
        data = await request_json("GET", "/api/relationships", params={"to": f"person:{first['id']}"})
        return data.get("items", data)
    second = await get_person(person_b)
    if not second:
        return []
    outgoing = await request_json("GET", "/api/relationships", params={"from": f"person:{first['id']}", "to": f"person:{second['id']}"})
    incoming = await request_json("GET", "/api/relationships", params={"from": f"person:{second['id']}", "to": f"person:{first['id']}"})
    return (outgoing.get("items") or []) + (incoming.get("items") or [])


async def get_recent_events(person: str | None = None, days: int = 30) -> list[dict[str, Any]]:
    since = (date.today() - timedelta(days=days)).isoformat()
    params: dict[str, Any] = {"since": since}
    if person:
        matched = await get_person(person)
        if not matched:
            return []
        params["person_id"] = matched["id"]
    data = await request_json("GET", "/api/events", params=params)
    return data.get("items", data)


async def get_self_profile() -> dict[str, Any]:
    return await request_json("GET", "/api/self")


async def get_timeline(person: str | None = None, stage: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if stage:
        stages = await request_json("GET", "/api/stages")
        for item in stages.get("items", []):
            if item.get("name") == stage:
                params["stage_id"] = item["id"]
                break
    timeline = await request_json("GET", "/api/timeline", params=params)
    if person:
        for stage_item in timeline.get("stages", []):
            stage_item["people"] = [item for item in stage_item.get("people", []) if item.get("name") == person]
    return timeline
