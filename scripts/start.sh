#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

mkdir -p data/uploads data/exports

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker compose up -d
  echo "Frontend: http://localhost:3000"
  echo "Backend:  http://localhost:8000/docs"
  exit 0
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv. Run npm install first." >&2
  exit 1
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///$(pwd)/data/dossier.db}" \
UPLOAD_DIR="${UPLOAD_DIR:-$(pwd)/data/uploads}" \
EXPORT_DIR="${EXPORT_DIR:-$(pwd)/data/exports}" \
.venv/bin/alembic -c backend/alembic.ini upgrade head

pids=()
cleanup() {
  for pid in "${pids[@]}"; do
    kill "${pid}" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  DATABASE_URL="${DATABASE_URL:-sqlite:///$(pwd)/data/dossier.db}" \
  UPLOAD_DIR="${UPLOAD_DIR:-$(pwd)/data/uploads}" \
  EXPORT_DIR="${EXPORT_DIR:-$(pwd)/data/exports}" \
  .venv/bin/uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000 &
  pids+=("$!")
fi

echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/docs"
npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 3000 &
pids+=("$!")

wait
