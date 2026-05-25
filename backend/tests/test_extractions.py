from test_crud_api import unwrap


def send_chat_message(client, session_id: int, content: str):
    with client.stream("POST", f"/api/chat/sessions/{session_id}/messages", json={"content": content}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: done" in body


def test_end_session_extracts_auto_event_and_pending_relationship(client):
    person = unwrap(client.post("/api/people", json={"name": "老板", "aliases": ["张总"], "bio": "直属上级"}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "抽取验证"}))
    send_chat_message(client, session["session_id"], "老板今天又说我加班不够，该怎么回？")

    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))
    assert ended["ended_at"] is not None
    assert ended["extractions"]["created"] >= 2
    assert ended["extractions"]["auto_applied"] == 1
    assert ended["extractions"]["pending"] >= 1

    events = unwrap(client.get("/api/events", params={"person_id": person["id"]}))
    assert events["items"][0]["source_session_id"] == session["session_id"]
    assert "加班不够" in events["items"][0]["title"]

    pending = unwrap(client.get("/api/extractions"))
    relationship = next(item for item in pending["items"] if item["kind"] == "relationship_new")
    assert relationship["status"] == "pending"
    assert relationship["payload"]["to_id"] == person["id"]

    accepted = unwrap(client.post(f"/api/extractions/{relationship['id']}/accept"))
    assert accepted["status"] == "accepted"
    relationships = unwrap(client.get("/api/relationships", params={"to": f"person:{person['id']}"}))
    assert relationships["items"][0]["role"] == "老板"


def test_reject_and_bulk_extraction_actions(client):
    person = unwrap(client.post("/api/people", json={"name": "经理", "aliases": ["老板"]}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "批量审核"}))
    send_chat_message(client, session["session_id"], "老板是我的直属上级，我其实很怕被催。")
    unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    pending = unwrap(client.get("/api/extractions"))
    relationship = next(item for item in pending["items"] if item["kind"] == "relationship_new")
    self_update = next(item for item in pending["items"] if item["kind"] == "self_update")

    rejected = unwrap(client.post(f"/api/extractions/{self_update['id']}/reject"))
    assert rejected["status"] == "rejected"

    bulk = unwrap(client.post("/api/extractions/bulk", json={"accept": [relationship["id"]], "reject": []}))
    assert bulk["accepted"] == [relationship["id"]]
    assert bulk["rejected"] == []

    relationships = unwrap(client.get("/api/relationships", params={"to": f"person:{person['id']}"}))
    assert relationships["items"][0]["relation_type"] == "上下级"
    self_profile = unwrap(client.get("/api/self"))
    assert "被催" not in (self_profile["sensitivities"] or [])


def test_edit_pending_extraction_before_accept(client):
    person = unwrap(client.post("/api/people", json={"name": "负责人", "aliases": ["老板"]}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "编辑审核"}))
    send_chat_message(client, session["session_id"], "老板是我的直属上级。")
    unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    pending = unwrap(client.get("/api/extractions"))
    relationship = next(item for item in pending["items"] if item["kind"] == "relationship_new")
    edited_payload = {
        **relationship["payload"],
        "relation_type": "协作",
        "role": "项目负责人",
        "notes": "人工编辑后接受。",
    }

    updated = unwrap(client.patch(f"/api/extractions/{relationship['id']}", json={"payload": edited_payload, "confidence": 0.88}))
    assert updated["payload"]["relation_type"] == "协作"
    assert updated["confidence"] == 0.88

    accepted = unwrap(client.post(f"/api/extractions/{relationship['id']}/accept"))
    assert accepted["status"] == "accepted"
    relationships = unwrap(client.get("/api/relationships", params={"to": f"person:{person['id']}"}))
    assert relationships["items"][0]["relation_type"] == "协作"
    assert relationships["items"][0]["role"] == "项目负责人"
    assert relationships["items"][0]["notes"] == "人工编辑后接受。"


def test_repair_pending_extraction_payload_with_extraction_model(client, monkeypatch):
    unwrap(client.patch("/api/settings", json={"extraction_model": "ollama/qwen2.5"}))
    unwrap(
        client.post(
            "/api/import/llm-memory",
            json={
                "json": """
                {
                  "events": [
                    {
                      "occurred_at": "近期",
                      "title": "米饼事件",
                      "description": "户外散步时女儿想踩落地零食。",
                      "participants": ["用户本人", "妻子", "女儿", "母亲"]
                    }
                  ]
                }
                """
            },
        )
    )
    event = next(item for item in unwrap(client.get("/api/extractions"))["items"] if item["kind"] == "event_new")
    calls = []

    class FakeLLMClient:
        def complete_json(self, model, messages):
            calls.append({"model": model, "messages": messages})
            return {"payload": {**event["payload"], "occurred_at": None}}

    monkeypatch.setattr("app.api.extractions.LLMClient", FakeLLMClient, raising=False)

    repaired = unwrap(client.post(f"/api/extractions/{event['id']}/repair", json={"error": "Invalid isoformat string: '近期'"}))

    assert calls and calls[0]["model"] == "ollama/qwen2.5"
    assert "Invalid isoformat string" in calls[0]["messages"][0]["content"]
    assert repaired["status"] == "pending"
    assert repaired["target_id"] is None
    assert repaired["payload"]["occurred_at"] is None
    assert unwrap(client.get("/api/events"))["items"] == []

    accepted = unwrap(client.post(f"/api/extractions/{event['id']}/accept"))
    assert accepted["status"] == "accepted"
    events = unwrap(client.get("/api/events"))["items"]
    assert events[0]["title"] == "米饼事件"
    assert events[0]["occurred_at"] is None


def test_undo_auto_applied_extraction_deletes_created_event(client):
    person = unwrap(client.post("/api/people", json={"name": "老板"}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "撤销自动应用"}))
    send_chat_message(client, session["session_id"], "老板今天又提醒我进度。")
    unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    auto_applied = unwrap(client.get("/api/extractions", params={"status": "auto_applied"}))
    event_extraction = next(item for item in auto_applied["items"] if item["kind"] == "event_new")
    assert event_extraction["target_id"] is not None
    events_before = unwrap(client.get("/api/events", params={"person_id": person["id"]}))
    assert [item["id"] for item in events_before["items"]] == [event_extraction["target_id"]]

    undone = unwrap(client.post(f"/api/extractions/{event_extraction['id']}/undo"))
    assert undone["status"] == "rejected"
    events_after = unwrap(client.get("/api/events", params={"person_id": person["id"]}))
    assert events_after["items"] == []


def test_unknown_boss_extraction_can_seed_person_for_future_retrieval(client):
    session = unwrap(client.post("/api/chat/sessions", json={"title": "新人物抽取"}))
    send_chat_message(client, session["session_id"], "我老板今天又说我加班不够。")
    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))
    assert ended["extractions"]["pending"] >= 1

    pending = unwrap(client.get("/api/extractions"))
    person_extraction = next(item for item in pending["items"] if item["kind"] == "person_new")
    assert person_extraction["payload"]["name"] == "老板"

    accepted = unwrap(client.post(f"/api/extractions/{person_extraction['id']}/accept"))
    assert accepted["status"] == "accepted"
    people = unwrap(client.get("/api/people", params={"q": "老板"}))
    assert [person["name"] for person in people["items"]] == ["老板"]

    follow_up = unwrap(client.post("/api/chat/sessions", json={"title": "后续 retrieval"}))
    send_chat_message(client, follow_up["session_id"], "老板今天又提醒我进度。")
    loaded = unwrap(client.get(f"/api/chat/sessions/{follow_up['session_id']}"))
    user_message = next(message for message in loaded["messages"] if message["role"] == "user")
    assert [person["name"] for person in user_message["context_used"]["people"]] == ["老板"]


def test_extraction_matches_person_alias_with_token_sort(client):
    person = unwrap(client.post("/api/people", json={"name": "张总", "aliases": ["Alice Zhang"]}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "alias matcher"}))
    send_chat_message(client, session["session_id"], "Zhang Alice 今天又提醒我进度。")

    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))
    assert ended["extractions"]["auto_applied"] == 1
    events = unwrap(client.get("/api/events", params={"person_id": person["id"]}))
    assert events["items"][0]["participants"] == [{"type": "person", "id": person["id"]}]


def test_extraction_runner_uses_model_json_output(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "张总"}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "model extraction"}))
    send_chat_message(client, session["session_id"], "今天有个重要变化。")

    calls = []

    class FakeLLMClient:
        def complete_json(self, model, messages):
            calls.append({"model": model, "messages": messages})
            return {
                "events": [
                    {
                        "occurred_at": "2026-05-23",
                        "title": "模型抽取事件",
                        "description": "由 extraction_model 返回。",
                        "participants": [{"type": "person", "matched_id": person["id"]}],
                        "confidence": 0.9,
                    }
                ]
            }

    monkeypatch.setattr("app.extraction.runner.LLMClient", FakeLLMClient, raising=False)
    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    assert ended["extractions"] == {"created": 1, "auto_applied": 1, "pending": 0}
    assert calls and calls[0]["model"] == "anthropic/claude-haiku-4-5-20251001"
    events = unwrap(client.get("/api/events", params={"person_id": person["id"]}))
    assert events["items"][0]["title"] == "模型抽取事件"
    assert events["items"][0]["participants"] == [{"type": "person", "id": person["id"]}]


def test_model_json_maps_people_entities_relationships_and_self_updates(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "张总"}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "model extraction full"}))
    send_chat_message(client, session["session_id"], "今天聊到了新同事、新公司、上下级关系和我的敏感点。")

    class FakeLLMClient:
        def complete_json(self, model, messages):
            return {
                "people": [
                    {
                        "name_used": "新同事",
                        "matched_person_id": None,
                        "is_new": True,
                        "new_facts": {"bio": "从模型抽取的新同事", "profile_json": {"role": "设计"}},
                        "confidence": 0.8,
                    }
                ],
                "entities": [
                    {
                        "type": "company",
                        "name": "新公司",
                        "bio": "从模型抽取的新公司",
                        "profile_json": {"industry": "AI"},
                        "confidence": 0.88,
                    }
                ],
                "relationships": [
                    {
                        "from_type": "self",
                        "to_type": "person",
                        "to_id_or_name": person["id"],
                        "relation_type": "上下级",
                        "role": "老板",
                        "change_kind": "new",
                        "delta": {"notes": "模型认为需要人工确认"},
                        "confidence": 0.95,
                    }
                ],
                "self_updates": {
                    "patches": {"sensitivities": ["被催", "临时改需求"]},
                    "confidence": 0.7,
                },
            }

    monkeypatch.setattr("app.extraction.runner.LLMClient", FakeLLMClient, raising=False)
    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    assert ended["extractions"] == {"created": 4, "auto_applied": 0, "pending": 4}
    pending = unwrap(client.get("/api/extractions"))
    by_kind = {item["kind"]: item for item in pending["items"]}
    assert by_kind["person_new"]["payload"]["name"] == "新同事"
    assert by_kind["person_new"]["payload"]["profile_json"] == {"role": "设计"}
    assert by_kind["entity_new"]["payload"]["name"] == "新公司"
    assert by_kind["entity_new"]["payload"]["type"] == "company"
    assert by_kind["relationship_new"]["payload"]["to_id"] == person["id"]
    assert by_kind["relationship_new"]["payload"]["notes"] == "模型认为需要人工确认"
    assert by_kind["self_update"]["payload"] == {"patches": {"sensitivities": ["被催", "临时改需求"]}}


def test_model_relationship_target_name_resolves_existing_person(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "张总", "aliases": ["Alice Zhang"]}))
    session = unwrap(client.post("/api/chat/sessions", json={"title": "model relationship target name"}))
    send_chat_message(client, session["session_id"], "今天聊到了和张总的上下级关系。")

    class FakeLLMClient:
        def complete_json(self, model, messages):
            return {
                "relationships": [
                    {
                        "from_type": "self",
                        "to_type": "person",
                        "to_id_or_name": "Zhang Alice",
                        "relation_type": "上下级",
                        "role": "老板",
                        "change_kind": "new",
                        "confidence": 0.95,
                    }
                ]
            }

    monkeypatch.setattr("app.extraction.runner.LLMClient", FakeLLMClient, raising=False)
    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    assert ended["extractions"] == {"created": 1, "auto_applied": 0, "pending": 1}
    pending = unwrap(client.get("/api/extractions"))
    relationship = pending["items"][0]
    assert relationship["kind"] == "relationship_new"
    assert relationship["payload"]["to_id"] == person["id"]


def test_model_person_update_can_be_accepted_or_auto_applied(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "张总", "profile_json": {"style": "看重结果"}}))

    class FakeLLMClient:
        def complete_json(self, model, messages):
            return {
                "people": [
                    {
                        "name_used": "张总",
                        "matched_person_id": person["id"],
                        "is_new": False,
                        "new_facts": {"profile_json": {"style": "看重结果", "topic": "预算"}},
                        "confidence": 0.92,
                    }
                ]
            }

    monkeypatch.setattr("app.extraction.runner.LLMClient", FakeLLMClient, raising=False)

    pending_session = unwrap(client.post("/api/chat/sessions", json={"title": "pending person update"}))
    send_chat_message(client, pending_session["session_id"], "张总最近一直提预算。")
    ended = unwrap(client.post(f"/api/chat/sessions/{pending_session['session_id']}/end"))
    assert ended["extractions"] == {"created": 1, "auto_applied": 0, "pending": 1}

    pending = unwrap(client.get("/api/extractions"))
    update = pending["items"][0]
    assert update["kind"] == "person_update"
    assert update["payload"] == {"person_id": person["id"], "profile_json": {"style": "看重结果", "topic": "预算"}}

    accepted = unwrap(client.post(f"/api/extractions/{update['id']}/accept"))
    assert accepted["status"] == "accepted"
    detail = unwrap(client.get(f"/api/people/{person['id']}"))
    assert detail["person"]["profile_json"] == {"style": "看重结果", "topic": "预算"}

    unwrap(client.patch("/api/settings", json={"auto_extract_kinds": ["event_new", "person_new", "note_new", "person_update"]}))
    auto_session = unwrap(client.post("/api/chat/sessions", json={"title": "auto person update"}))
    send_chat_message(client, auto_session["session_id"], "张总继续提预算。")
    auto_ended = unwrap(client.post(f"/api/chat/sessions/{auto_session['session_id']}/end"))
    assert auto_ended["extractions"] == {"created": 1, "auto_applied": 1, "pending": 0}


def test_model_relationship_update_can_be_accepted(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "张总"}))
    relationship = unwrap(
        client.post(
            "/api/relationships",
            json={
                "from_type": "self",
                "to_type": "person",
                "to_id": person["id"],
                "relation_type": "上下级",
                "role": "老板",
                "status": "紧张",
            },
        )
    )

    class FakeLLMClient:
        def complete_json(self, model, messages):
            return {
                "relationships": [
                    {
                        "from_type": "self",
                        "to_type": "person",
                        "to_id_or_name": person["id"],
                        "relation_type": "上下级",
                        "role": "老板",
                        "change_kind": "update",
                        "delta": {"status": "缓和", "notes": "最近沟通改善"},
                        "confidence": 0.95,
                    }
                ]
            }

    monkeypatch.setattr("app.extraction.runner.LLMClient", FakeLLMClient, raising=False)
    session = unwrap(client.post("/api/chat/sessions", json={"title": "relationship update"}))
    send_chat_message(client, session["session_id"], "今天聊到了和张总关系缓和。")
    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))

    assert ended["extractions"] == {"created": 1, "auto_applied": 0, "pending": 1}
    pending = unwrap(client.get("/api/extractions"))
    update = pending["items"][0]
    assert update["kind"] == "relationship_update"
    assert update["payload"] == {"relationship_id": relationship["id"], "status": "缓和", "notes": "最近沟通改善"}

    accepted = unwrap(client.post(f"/api/extractions/{update['id']}/accept"))
    assert accepted["status"] == "accepted"
    updated = unwrap(client.get(f"/api/relationships/{relationship['id']}"))
    assert updated["status"] == "缓和"
    assert updated["notes"] == "最近沟通改善"
