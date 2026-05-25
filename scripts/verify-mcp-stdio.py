from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "interpret_message",
    "prepare_conversation",
    "stale_contacts",
    "recent_changes",
    "get_person",
    "search_people",
    "get_relationship",
    "get_recent_events",
    "get_self_profile",
    "get_timeline",
}

TOOL_ARGUMENTS = {
    "interpret_message": {
        "message": "老板说我最近加班比较多啊",
        "from_hint": "老板",
        "context_hint": "日常沟通",
    },
    "prepare_conversation": {
        "with_person": "老板",
        "desired_outcome": "推进项目",
        "scenario": "周会前",
    },
    "stale_contacts": {
        "days": 30,
    },
    "recent_changes": {
        "person": "老板",
        "days": 7,
    },
    "get_person": {
        "name_or_id": "老板",
    },
    "get_relationship": {
        "person_a": "老板",
    },
    "get_recent_events": {
        "person": "老板",
        "days": 30,
    },
    "get_self_profile": {},
    "get_timeline": {
        "person": "老板",
        "stage": "工作",
    },
    "search_people": {
        "query": "老板",
        "limit": 5,
    },
}


async def list_stdio_tools(server_path: Path, api_url: str) -> set[str]:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={**os.environ, "DOSSIER_API_URL": api_url},
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
    return {tool.name for tool in result.tools}


async def call_stdio_tool(server_path: Path, api_url: str, tool_name: str) -> str:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={**os.environ, "DOSSIER_API_URL": api_url},
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, TOOL_ARGUMENTS[tool_name])
    return str(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Dossier MCP stdio tool registration.")
    parser.add_argument("--api-url", default=os.environ.get("DOSSIER_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--call-tool", choices=sorted(TOOL_ARGUMENTS))
    parser.add_argument("--call-all", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    server_path = project_root / "mcp" / "server.py"
    tools = anyio.run(list_stdio_tools, server_path, args.api_url)
    missing = sorted(EXPECTED_TOOLS - tools)
    if missing:
        print("Missing MCP tools: " + ", ".join(missing), file=sys.stderr)
        return 1
    print("MCP stdio tools OK: " + ", ".join(sorted(tools)))
    tool_names = sorted(TOOL_ARGUMENTS) if args.call_all else ([args.call_tool] if args.call_tool else [])
    for tool_name in tool_names:
        output = anyio.run(call_stdio_tool, server_path, args.api_url, tool_name)
        print(f"MCP stdio call OK: {tool_name}")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
