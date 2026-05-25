# Dossier

Local-first relationship dossier for Chinese interpersonal communication.

## Quickstart

```bash
git clone https://github.com/UntR/TencentDB-Agent-Memory.git dossier
cd dossier && npm install
npm start
```

Frontend: `http://localhost:3000`

Backend API docs: `http://localhost:8000/docs`

## Screenshots

![Chat](docs/screenshots/chat.png)

![Inbox](docs/screenshots/inbox.png)

![Timeline](docs/screenshots/timeline.png)

## Common Commands

```bash
npm start
npm stop
npm run build
npm run test:e2e
.venv/bin/python -m pytest backend/tests -q
scripts/install-mcp.sh --write-claude-config
scripts/install-backup-cron.sh --dry-run
```

## Troubleshooting

### 路径校验失败

Run `pwd` from the repository root and make sure `.env`, `data/`, `backend/`, `frontend/`, and `mcp/` are in the same directory. If the SQLite path is wrong, remove the bad `DATABASE_URL` override from `.env` and rerun `npm start`.

### API key 不识别

Provider keys are read from `.env` / environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `GOOGLE_API_KEY`. Restart `npm start` after editing `.env`. Extraction and chat models are configured separately in Settings.

### MCP 装不上

Run `npm install` first so `.venv` and MCP dependencies exist, then run:

```bash
scripts/install-mcp.sh --write-claude-config
```

Restart Claude Desktop after writing config. If tools still do not appear, verify stdio directly:

```bash
.venv/bin/python scripts/verify-mcp-stdio.py
```
