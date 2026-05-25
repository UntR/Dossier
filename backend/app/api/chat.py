from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import missing, model_dict, ok
from app.chat.orchestrator import stream_chat_response
from app.db.models import ChatMessage, ChatSession
from app.db.session import get_db
from app.extraction.runner import run_extraction_for_session
from app.llm.streaming import sse_event

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)


@router.post("/sessions")
def create_session(payload: ChatSessionCreate | None = None, db: Session = Depends(get_db)):
    session = ChatSession(title=payload.title if payload else None)
    db.add(session)
    db.commit()
    db.refresh(session)
    return ok({"session_id": session.id})


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.scalars(select(ChatSession).order_by(ChatSession.started_at.desc())).all()
    return ok({"items": [model_dict(session) for session in sessions]})


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if session is None:
        missing("chat session")
    messages = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc())).all()
    return ok({**model_dict(session), "messages": [model_dict(message) for message in messages]})


@router.post("/sessions/{session_id}/messages")
def post_message(session_id: int, payload: ChatMessageCreate, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")

    context, chunks = stream_chat_response(db, payload.content, session_id=session_id)
    user_message = ChatMessage(session_id=session_id, role="user", content=payload.content, context_used=context)
    db.add(user_message)
    db.commit()

    def stream():
        assistant_parts = []
        yield sse_event("context", context)
        for chunk in chunks:
            assistant_parts.append(chunk)
            yield sse_event("delta", {"content": chunk})
        assistant_content = "".join(assistant_parts)
        db.add(ChatMessage(session_id=session_id, role="assistant", content=assistant_content, context_used=context))
        db.commit()
        yield sse_event("done", {"ok": True})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/end")
def end_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if session is None:
        missing("chat session")
    session.ended_at = datetime.now(UTC).replace(tzinfo=None)
    extraction_summary = run_extraction_for_session(db, session_id)
    db.commit()
    db.refresh(session)
    return ok({**model_dict(session), "extractions": extraction_summary})


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if session is None:
        missing("chat session")
    db.delete(session)
    db.commit()
    return ok({"id": session_id})
