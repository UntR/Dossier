from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tools.data import get_person as data_get_person
from tools.data import get_recent_events as data_get_recent_events
from tools.data import get_relationship as data_get_relationship
from tools.data import get_self_profile as data_get_self_profile
from tools.data import get_timeline as data_get_timeline
from tools.data import search_people as data_search_people
from tools.intent import interpret_message as intent_interpret_message
from tools.intent import prepare_conversation as intent_prepare_conversation
from tools.intent import recent_changes as intent_recent_changes
from tools.intent import stale_contacts as intent_stale_contacts


mcp = FastMCP("Dossier")


@mcp.tool()
async def interpret_message(message: str, from_hint: str | None = None, context_hint: str | None = None) -> dict[str, Any]:
    """解读一条收到的消息，给出潜台词分析和备选回复。"""
    return await intent_interpret_message(message, from_hint, context_hint)


@mcp.tool()
async def prepare_conversation(
    with_person: str,
    desired_outcome: str | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    """准备和某个人的一次沟通。"""
    return await intent_prepare_conversation(with_person, desired_outcome, scenario)


@mcp.tool()
async def stale_contacts(days: int = 30) -> list[dict[str, Any]]:
    """列出最近一段时间没有互动记录的人。"""
    return await intent_stale_contacts(days)


@mcp.tool()
async def recent_changes(person: str | None = None, days: int = 7) -> list[dict[str, Any]]:
    """列出最近的人际事件变化。"""
    return await intent_recent_changes(person, days)


@mcp.tool()
async def get_person(name_or_id: str) -> dict[str, Any] | None:
    """按姓名、别名或 ID 查询人物 dossier。"""
    return await data_get_person(name_or_id)


@mcp.tool()
async def search_people(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """搜索人物。"""
    return await data_search_people(query, limit)


@mcp.tool()
async def get_relationship(person_a: str, person_b: str | None = None) -> list[dict[str, Any]]:
    """查询两个人之间的关系；不传 person_b 时查询 self 和 person_a 的关系。"""
    return await data_get_relationship(person_a, person_b)


@mcp.tool()
async def get_recent_events(person: str | None = None, days: int = 30) -> list[dict[str, Any]]:
    """查询最近事件，可按人物过滤。"""
    return await data_get_recent_events(person, days)


@mcp.tool()
async def get_self_profile() -> dict[str, Any]:
    """查询用户自己的画像。"""
    return await data_get_self_profile()


@mcp.tool()
async def get_timeline(person: str | None = None, stage: str | None = None) -> dict[str, Any]:
    """查询时间树，可按人物或阶段过滤。"""
    return await data_get_timeline(person, stage)


if __name__ == "__main__":
    mcp.run()
