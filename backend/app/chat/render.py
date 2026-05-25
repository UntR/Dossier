from __future__ import annotations

import json

from app.llm.prompts.chat_system import CHAT_SYSTEM_TEMPLATE


def render_chat_system_prompt(context: dict) -> str:
    self_profile = context.get("self") or {}
    self_rendered = json.dumps(self_profile, ensure_ascii=False, indent=2)
    people_rendered = []
    for person in context.get("people", []):
        related_events = [event for event in context.get("events", []) if _event_mentions(event, person["id"])]
        people_rendered.append(
            json.dumps(
                {
                    "姓名": person.get("name"),
                    "别名": person.get("aliases"),
                    "简介": person.get("bio"),
                    "画像": person.get("profile_json"),
                    "最近事件": related_events,
                },
                ensure_ascii=False,
            )
        )
    return CHAT_SYSTEM_TEMPLATE.format(
        self_name=self_profile.get("name", "我"),
        self_profile=self_rendered,
        people="\n".join(people_rendered) or "无",
        entities=json.dumps(context.get("entities", []), ensure_ascii=False, indent=2),
    )


def _event_mentions(event: dict, person_id: int) -> bool:
    return any(participant.get("type") == "person" and participant.get("id") == person_id for participant in event.get("participants") or [])
