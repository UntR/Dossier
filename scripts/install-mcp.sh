#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

write_claude_config=0
for arg in "$@"; do
  case "$arg" in
    --write-claude-config)
      write_claude_config=1
      ;;
    -h|--help)
      echo "Usage: scripts/install-mcp.sh [--write-claude-config]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ -x ".venv/bin/python" ]]; then
  python_cmd="$(pwd)/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_cmd="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_cmd="$(command -v python)"
else
  echo "No Python interpreter found. Create .venv or install python3." >&2
  exit 1
fi

"${python_cmd}" -m pip install -r mcp/requirements.txt

server_path="$(pwd)/mcp/server.py"

if [[ "${write_claude_config}" -eq 1 ]]; then
  claude_config_path="${HOME}/Library/Application Support/Claude/claude_desktop_config.json"
  "${python_cmd}" - "${claude_config_path}" "${python_cmd}" "${server_path}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
python_cmd = sys.argv[2]
server_path = sys.argv[3]

config_path.parent.mkdir(parents=True, exist_ok=True)
if config_path.exists():
    raw = config_path.read_text(encoding="utf-8").strip()
    config = json.loads(raw) if raw else {}
    backup_path = config_path.with_name(config_path.name + ".bak")
    backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
else:
    config = {}

if not isinstance(config, dict):
    raise SystemExit("Claude Desktop config must be a JSON object")

mcp_servers = config.setdefault("mcpServers", {})
if not isinstance(mcp_servers, dict):
    raise SystemExit("Claude Desktop config mcpServers must be a JSON object")

mcp_servers["dossier"] = {
    "command": python_cmd,
    "args": [server_path],
    "env": {"DOSSIER_API_URL": "http://127.0.0.1:8000"},
}

config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  echo "Wrote Claude Desktop config: ${claude_config_path}"
  echo "Restart Claude Desktop to load the dossier MCP server."
else
  cat <<JSON
Add this to Claude Desktop config:

{
  "mcpServers": {
    "dossier": {
      "command": "${python_cmd}",
      "args": ["${server_path}"],
      "env": {
        "DOSSIER_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
JSON
fi
