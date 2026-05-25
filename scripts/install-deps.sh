#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -x ".venv/bin/python" ]]; then
  python_cmd=".venv/bin/python"
else
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  elif command -v python >/dev/null 2>&1; then
    python -m venv .venv
  else
    echo "Python 3 is required. Install Python, then rerun npm install." >&2
    exit 1
  fi
  python_cmd=".venv/bin/python"
fi

if ! PYTHONPATH=backend "${python_cmd}" - <<'PY'
import alembic
import app
import fastapi
import httpx
import mcp
import pytest
import sqlalchemy
PY
then
  "${python_cmd}" -m pip install -e "backend[test]" -r mcp/requirements.txt
fi
npm --prefix frontend install
