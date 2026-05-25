from __future__ import annotations

from test_chat import seed_boss_context
from test_crud_api import unwrap


def test_mcp_interpret_returns_fixed_json_shape_with_matched_sender(client):
    seed_boss_context(client)

    result = unwrap(
        client.post(
            "/api/mcp/interpret",
            json={"message": "老板说我最近加班比较多啊", "from_hint": "张总", "context_hint": "周报"},
        )
    )

    assert result["sender"]["matched_person"]["name"] == "老板"
    assert result["sender"]["confidence"] >= 0.8
    assert result["literal_meaning"]
    assert result["possible_meanings"][0]["probability"] in {"高", "中", "低"}
    assert len(result["reply_options"]) == 3
    assert {item["tone"] for item in result["reply_options"]} == {"克制", "中性", "主动"}


def test_mcp_interpret_uses_chat_model_json_when_available(client, monkeypatch):
    seed_boss_context(client)
    calls = []

    class FakeLLMClient:
        def complete_json(self, model, messages):
            calls.append({"model": model, "messages": messages})
            return {
                "possible_meanings": [{"interpretation": "模型判断是在催进度。", "probability": "高"}],
                "recommended_outcome": "先承接进度压力，再给出今天的交付边界。",
                "reply_options": [
                    {"tone": "克制", "text": "我会先同步当前进度和风险。", "rationale": "承接压力。"},
                    {"tone": "中性", "text": "我今天给你一版进展说明。", "rationale": "给出动作。"},
                ],
            }

    monkeypatch.setattr("app.api.mcp_intent.LLMClient", FakeLLMClient, raising=False)

    result = unwrap(
        client.post(
            "/api/mcp/interpret",
            json={"message": "老板说我最近加班比较多啊", "from_hint": "张总", "context_hint": "周报"},
        )
    )

    assert calls and calls[0]["model"] == "anthropic/claude-sonnet-4-6"
    assert "老板说我最近加班比较多啊" in calls[0]["messages"][0]["content"]
    assert result["sender"]["matched_person"]["name"] == "老板"
    assert result["possible_meanings"] == [{"interpretation": "模型判断是在催进度。", "probability": "高"}]
    assert result["recommended_outcome"] == "先承接进度压力，再给出今天的交付边界。"
    assert result["reply_options"][0]["text"] == "我会先同步当前进度和风险。"
    assert result["context_used"]["people"][0]["name"] == "老板"


def test_mcp_prepare_stale_contacts_and_recent_changes(client):
    person = seed_boss_context(client)

    prepare = unwrap(
        client.post(
            "/api/mcp/prepare",
            json={"with_person": "张总", "desired_outcome": "推进项目", "scenario": "周会前"},
        )
    )
    assert prepare["person"]["name"] == "老板"
    assert "推进项目" in prepare["suggested_opening"]
    assert prepare["relationship_summary"]
    assert prepare["recent_events"][0]["title"] == "周会被提醒进度"

    stale = unwrap(client.get("/api/mcp/stale-contacts", params={"days": 1}))
    assert all(item["person"]["id"] != person["id"] for item in stale["items"])

    changes = unwrap(client.get("/api/mcp/recent-changes", params={"person": "老板", "days": 30}))
    assert changes["items"][0]["kind"] == "event"
    assert changes["items"][0]["title"] == "周会被提醒进度"


def test_mcp_prepare_uses_chat_model_json_when_available(client, monkeypatch):
    seed_boss_context(client)
    calls = []

    class FakeLLMClient:
        def complete_json(self, model, messages):
            calls.append({"model": model, "messages": messages})
            return {
                "talking_points": ["先确认周会目标", "再同步当前风险"],
                "risks": ["避免只解释困难"],
                "suggested_opening": "这次周会前我先同步目标、进度和需要你拍板的点。",
            }

    monkeypatch.setattr("app.api.mcp_intent.LLMClient", FakeLLMClient, raising=False)

    prepare = unwrap(
        client.post(
            "/api/mcp/prepare",
            json={"with_person": "张总", "desired_outcome": "推进项目", "scenario": "周会前"},
        )
    )

    assert calls and calls[0]["model"] == "anthropic/claude-sonnet-4-6"
    assert "张总" in calls[0]["messages"][0]["content"]
    assert prepare["person"]["name"] == "老板"
    assert prepare["recent_events"][0]["title"] == "周会被提醒进度"
    assert prepare["talking_points"] == ["先确认周会目标", "再同步当前风险"]
    assert prepare["risks"] == ["避免只解释困难"]
    assert prepare["suggested_opening"] == "这次周会前我先同步目标、进度和需要你拍板的点。"
