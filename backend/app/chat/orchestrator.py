from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.api.settings import read_settings
from app.chat.render import render_chat_system_prompt
from app.chat.retrieval import retrieve_context
from app.llm.client import LLMClient


def stream_chat_response(db: Session, user_message: str, session_id: int | None = None) -> tuple[dict, Iterator[str]]:
    context = retrieve_context(db, user_message, session_id=session_id)
    prompt = render_chat_system_prompt(context)
    settings = read_settings(db)
    model = settings.get("chat_model", "anthropic/claude-sonnet-4-6")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_message},
    ]
    return context, LLMClient().stream_chat(model, messages)
