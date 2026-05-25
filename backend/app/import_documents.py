from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_import_markdown(source: str, title: str, body: str, metadata: dict[str, Any] | None = None) -> dict[str, str]:
    imports_dir = import_documents_dir()
    imports_dir.mkdir(parents=True, exist_ok=True)
    path = imports_dir / f"{timestamp_slug()}-{safe_slug(title)}-{uuid4().hex[:8]}.md"
    path.write_text(render_import_markdown(source, title, body, metadata or {}), encoding="utf-8")
    return {"path": str(path), "filename": path.name}


def import_documents_dir() -> Path:
    upload_dir = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
    return upload_dir.parent / "imports"


def render_import_markdown(source: str, title: str, body: str, metadata: dict[str, Any]) -> str:
    frontmatter = {
        "source": source,
        "created_at": datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds"),
        **metadata,
    }
    lines = ["---", *[f"{key}: {frontmatter_value(value)}" for key, value in frontmatter.items()], "---", "", f"# {title}", "", body.strip(), ""]
    return "\n".join(lines)


def frontmatter_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    return text if re.fullmatch(r"[\w./:@-]+", text) else json.dumps(text, ensure_ascii=False)


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", value).strip("-._")
    return slug[:48] or "import"
