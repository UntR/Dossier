from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import model_dict, ok, text_matches
from app.api.settings import read_settings
from app.chat.retrieval import retrieve_context
from app.db.models import Event, Person, Relationship
from app.db.session import get_db
from app.llm.client import LLMClient

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class InterpretRequest(BaseModel):
    message: str
    from_hint: str | None = None
    context_hint: str | None = None


class PrepareRequest(BaseModel):
    with_person: str
    desired_outcome: str | None = None
    scenario: str | None = None


@router.post("/interpret")
def interpret_message(payload: InterpretRequest, db: Session = Depends(get_db)):
    lookup_text = " ".join(item for item in [payload.message, payload.from_hint] if item)
    context = retrieve_context(db, lookup_text)
    matched_person = _first_person(context)
    relationship = _first_relationship(context, matched_person)
    response = {
        "sender": {
            "matched_person": matched_person,
            "confidence": _sender_confidence(matched_person, payload.from_hint, payload.message),
        },
        "literal_meaning": payload.message,
        "possible_meanings": _possible_meanings(payload.message, relationship),
        "recommended_outcome": _recommended_outcome(payload.context_hint, relationship),
        "reply_options": _reply_options(payload.message, relationship),
        "context_used": context,
    }
    model_output = LLMClient().complete_json(
        read_settings(db).get("chat_model", "anthropic/claude-sonnet-4-6"),
        _interpret_messages(payload, context),
    )
    if model_output:
        response.update(_model_interpret_fields(model_output))
    return ok(response)


def _interpret_messages(payload: InterpretRequest, context: dict[str, Any]) -> list[dict[str, str]]:
    prompt = (
        "你是用户的人际消息解读助手。只输出 JSON，无任何解释。\n"
        "请基于消息和已检索到的关系图谱上下文，给出潜台词、建议目标和备选回复。\n"
        "输出字段只包含 possible_meanings, recommended_outcome, reply_options。\n\n"
        f"# 消息\n{payload.message}\n"
        f"# 发送人提示\n{payload.from_hint or ''}\n"
        f"# 场景提示\n{payload.context_hint or ''}\n"
        f"# 上下文\n{context}"
    )
    return [{"role": "user", "content": prompt}]


def _model_interpret_fields(output: dict[str, Any]) -> dict[str, Any]:
    fields = {}
    if isinstance(output.get("possible_meanings"), list):
        fields["possible_meanings"] = output["possible_meanings"]
    if isinstance(output.get("recommended_outcome"), str):
        fields["recommended_outcome"] = output["recommended_outcome"]
    if isinstance(output.get("reply_options"), list):
        fields["reply_options"] = output["reply_options"]
    return fields


@router.post("/prepare")
def prepare_conversation(payload: PrepareRequest, db: Session = Depends(get_db)):
    person = _find_person(db, payload.with_person)
    relationships = _relationships_for_person(db, person.id) if person else []
    events = _recent_events_for_person(db, person.id, 10) if person else []
    desired_outcome = payload.desired_outcome or "把话说清楚，同时保留关系余地"
    scenario = payload.scenario or "下一次沟通"
    response = {
        "person": model_dict(person) if person else None,
        "scenario": scenario,
        "desired_outcome": desired_outcome,
        "relationship_summary": _relationship_summary(relationships),
        "recent_events": [model_dict(item) for item in events],
        "talking_points": _talking_points(person, desired_outcome, events),
        "risks": _conversation_risks(relationships),
        "suggested_opening": f"这次{scenario}我想先对齐目标：{desired_outcome}。",
    }
    model_output = LLMClient().complete_json(
        read_settings(db).get("chat_model", "anthropic/claude-sonnet-4-6"),
        _prepare_messages(payload, response),
    )
    if model_output:
        response.update(_model_prepare_fields(model_output))
    return ok(response)


def _prepare_messages(payload: PrepareRequest, response: dict[str, Any]) -> list[dict[str, str]]:
    prompt = (
        "你是用户的人际沟通准备助手。只输出 JSON，无任何解释。\n"
        "请基于已检索到的人物、关系和事件上下文，给出沟通要点、风险和开场建议。\n"
        "输出字段只包含 talking_points, risks, suggested_opening。\n\n"
        f"# 对象\n{payload.with_person}\n"
        f"# 目标\n{response['desired_outcome']}\n"
        f"# 场景\n{response['scenario']}\n"
        f"# 上下文\n{response}"
    )
    return [{"role": "user", "content": prompt}]


def _model_prepare_fields(output: dict[str, Any]) -> dict[str, Any]:
    fields = {}
    if isinstance(output.get("talking_points"), list):
        fields["talking_points"] = output["talking_points"]
    if isinstance(output.get("risks"), list):
        fields["risks"] = output["risks"]
    if isinstance(output.get("suggested_opening"), str):
        fields["suggested_opening"] = output["suggested_opening"]
    return fields


@router.get("/stale-contacts")
def stale_contacts(days: int = 30, db: Session = Depends(get_db)):
    cutoff = date.today() - timedelta(days=days)
    items = []
    for person in db.scalars(select(Person).order_by(Person.name.asc())).all():
        last_event = _latest_event_for_person(db, person.id)
        if last_event and last_event.occurred_at and last_event.occurred_at >= cutoff:
            continue
        days_since = (date.today() - last_event.occurred_at).days if last_event and last_event.occurred_at else None
        items.append(
            {
                "person": model_dict(person),
                "last_event": model_dict(last_event) if last_event else None,
                "days_since_last_event": days_since,
                "reason": f"{days} 天内没有记录到互动",
            }
        )
    return ok({"items": items})


@router.get("/recent-changes")
def recent_changes(person: str | None = None, days: int = 7, db: Session = Depends(get_db)):
    cutoff = date.today() - timedelta(days=days)
    matched_person = _find_person(db, person) if person else None
    events = db.scalars(select(Event).order_by(Event.occurred_at.desc(), Event.id.desc())).all()
    items = []
    for event in events:
        if event.occurred_at and event.occurred_at < cutoff:
            continue
        if matched_person and not _event_mentions_person(event, matched_person.id):
            continue
        items.append(
            {
                "kind": "event",
                "id": event.id,
                "title": event.title,
                "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
                "payload": model_dict(event),
            }
        )
    return ok({"items": items})


def _first_person(context: dict[str, Any]) -> dict[str, Any] | None:
    people = context.get("people") or []
    return people[0] if people else None


def _first_relationship(context: dict[str, Any], person: dict[str, Any] | None) -> dict[str, Any] | None:
    if not person:
        return None
    person_id = person.get("id")
    for relationship in context.get("relationships") or []:
        if relationship.get("from_id") == person_id or relationship.get("to_id") == person_id:
            return relationship
    return None


def _sender_confidence(person: dict[str, Any] | None, from_hint: str | None, message: str) -> float:
    if not person:
        return 0.0
    if from_hint and (from_hint == person.get("name") or text_matches(person.get("aliases"), from_hint)):
        return 0.95
    if str(person.get("name") or "") in message:
        return 0.9
    return 0.75


def _possible_meanings(message: str, relationship: dict[str, Any] | None) -> list[dict[str, str]]:
    relation_type = str((relationship or {}).get("relation_type") or "")
    role = str((relationship or {}).get("role") or "")
    if "加班" in message or "进度" in message:
        return [
            {"interpretation": "对方可能在提醒你关注产出和节奏，而不只是讨论加班本身。", "probability": "高"},
            {"interpretation": "如果对方语气温和，也可能是在试探你最近负荷是否过高。", "probability": "中"},
        ]
    if "上下级" in relation_type or "老板" in role:
        return [{"interpretation": "这条消息更可能带有管理预期，需要回应行动和边界。", "probability": "中"}]
    return [{"interpretation": "先按字面理解，同时保留对关系背景的观察。", "probability": "中"}]


def _recommended_outcome(context_hint: str | None, relationship: dict[str, Any] | None) -> str:
    if relationship:
        return f"先承接对方关注点，再给出下一步行动；场景：{context_hint or '日常沟通'}。"
    return f"先确认对方意图，再决定是否推进；场景：{context_hint or '日常沟通'}。"


def _reply_options(message: str, relationship: dict[str, Any] | None) -> list[dict[str, str]]:
    relation_label = str((relationship or {}).get("role") or (relationship or {}).get("relation_type") or "对方")
    return [
        {"tone": "克制", "text": "收到，我会先把当前进展和风险梳理清楚。", "rationale": f"先承接{relation_label}的关注点，不急着解释。"},
        {"tone": "中性", "text": "我理解你的意思。我今天会同步进度、卡点和下一步安排。", "rationale": "给出行动，降低对方继续追问的概率。"},
        {"tone": "主动", "text": "我补一版更清晰的计划给你，也会标出需要你拍板的地方。", "rationale": "把对话从被动解释转成推进事项。"},
    ]


def _find_person(db: Session, value: str | None) -> Person | None:
    if not value:
        return None
    if value.isdigit():
        person = db.get(Person, int(value))
        if person:
            return person
    people = db.scalars(select(Person).order_by(Person.importance.desc(), Person.name.asc())).all()
    for person in people:
        if person.name == value or text_matches(person.aliases, value):
            return person
    for person in people:
        if text_matches(person.name, value) or text_matches(person.bio, value) or text_matches(person.aliases, value):
            return person
    return None


def _relationships_for_person(db: Session, person_id: int) -> list[Relationship]:
    return db.scalars(
        select(Relationship).where(
            ((Relationship.from_type == "person") & (Relationship.from_id == person_id))
            | ((Relationship.to_type == "person") & (Relationship.to_id == person_id))
        )
    ).all()


def _recent_events_for_person(db: Session, person_id: int, limit: int) -> list[Event]:
    events = [
        event
        for event in db.scalars(select(Event).order_by(Event.occurred_at.desc(), Event.id.desc())).all()
        if _event_mentions_person(event, person_id)
    ]
    return events[:limit]


def _latest_event_for_person(db: Session, person_id: int) -> Event | None:
    events = _recent_events_for_person(db, person_id, 1)
    return events[0] if events else None


def _event_mentions_person(event: Event, person_id: int) -> bool:
    return any(participant.get("type") == "person" and participant.get("id") == person_id for participant in event.participants or [])


def _relationship_summary(relationships: list[Relationship]) -> str:
    if not relationships:
        return "暂无明确关系记录"
    return "；".join(f"{item.relation_type}，角色：{item.role or '未设置'}" for item in relationships)


def _talking_points(person: Person | None, desired_outcome: str, events: list[Event]) -> list[str]:
    points = [f"先说明本次目标：{desired_outcome}"]
    if person and person.bio:
        points.append(f"结合对方画像：{person.bio}")
    if events:
        points.append(f"可引用最近事件：{events[0].title}")
    return points


def _conversation_risks(relationships: list[Relationship]) -> list[str]:
    if any(item.relation_type == "上下级" for item in relationships):
        return ["避免只解释困难，要同步下一步动作和需要对方决策的点"]
    return ["避免一次性塞太多背景，先确认对方关注点"]
