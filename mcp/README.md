# Dossier MCP

Host-side MCP server for exposing Dossier to Claude Desktop and other MCP clients.

## Install

From the repository root:

```bash
scripts/install-mcp.sh
```

To merge Dossier into the local Claude Desktop config while preserving existing preferences:

```bash
scripts/install-mcp.sh --write-claude-config
```

The backend must be running before a client calls the tools. By default the MCP server calls:

```text
http://127.0.0.1:8000
```

Override it with `DOSSIER_API_URL`.

Verify stdio tool registration without Claude Desktop:

```bash
.venv/bin/python scripts/verify-mcp-stdio.py
```

Verify stdio tool invocation against a running backend:

```bash
.venv/bin/python scripts/verify-mcp-stdio.py --api-url http://127.0.0.1:8000 --call-tool interpret_message
```

## Claude Desktop

Add this server to Claude Desktop config:

```json
{
  "mcpServers": {
    "dossier": {
      "command": "/absolute/path/to/dossier/.venv/bin/python",
      "args": ["/absolute/path/to/dossier/mcp/server.py"],
      "env": {
        "DOSSIER_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

## Tools

Intent-level tools:

- `interpret_message`
- `prepare_conversation`
- `stale_contacts`
- `recent_changes`

Data-level tools:

- `get_person`
- `search_people`
- `get_relationship`
- `get_recent_events`
- `get_self_profile`
- `get_timeline`
