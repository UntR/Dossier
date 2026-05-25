from datetime import date

from test_crud_api import unwrap

from app.chat.render import render_chat_system_prompt
from app.chat.retrieval import retrieve_context
from sqlalchemy import event


def seed_boss_context(client):
    person = unwrap(
        client.post(
            "/api/people",
            json={"name": "老板", "aliases": ["张总"], "bio": "直属上级", "profile_json": {"style": "看重结果"}},
        )
    )
    unwrap(
        client.patch(
            "/api/self",
            json={"name": "我", "communication_style": "直接", "sensitivities": ["被催"]},
        )
    )
    unwrap(
        client.post(
            "/api/relationships",
            json={
                "from_type": "self",
                "to_type": "person",
                "to_id": person["id"],
                "relation_type": "上下级",
                "role": "老板",
            },
        )
    )
    unwrap(
        client.post(
            "/api/events",
            json={
                "occurred_at": date.today().isoformat(),
                "title": "周会被提醒进度",
                "participants": [{"type": "person", "id": person["id"]}],
                "source": "manual",
            },
        )
    )
    return person


def test_retrieval_and_render_include_matching_person_context(client):
    seed_boss_context(client)
    db = next(iter(client.app.dependency_overrides.values()))()
    session = next(db)
    try:
        context = retrieve_context(session, "老板说我最近加班比较多啊")
        prompt = render_chat_system_prompt(context)
    finally:
        session.close()

    assert context["people"][0]["name"] == "老板"
    assert "直属上级" in prompt
    assert "周会被提醒进度" in prompt
    assert "直接" in prompt


def test_retrieval_matches_person_alias_with_token_sort(client):
    unwrap(client.post("/api/people", json={"name": "张总", "aliases": ["Alice Zhang"], "bio": "项目负责人"}))
    db = next(iter(client.app.dependency_overrides.values()))()
    session = next(db)
    try:
        context = retrieve_context(session, "Zhang Alice")
    finally:
        session.close()

    assert [person["name"] for person in context["people"]] == ["张总"]


def test_retrieval_caches_same_session_person_context(client):
    seed_boss_context(client)
    db = next(iter(client.app.dependency_overrides.values()))()
    session = next(db)
    engine = session.get_bind()
    queries = []

    def count_query(*_):
        queries.append(1)

    event.listen(engine, "before_cursor_execute", count_query)
    try:
        retrieve_context(session, "老板说我最近加班比较多啊", session_id=101)
        first_query_count = len(queries)
        queries.clear()
        context = retrieve_context(session, "老板又问我进度了", session_id=101)
    finally:
        event.remove(engine, "before_cursor_execute", count_query)
        session.close()

    assert context["people"][0]["name"] == "老板"
    assert first_query_count > 1
    assert len(queries) <= 1


def test_chat_session_message_stream_records_context(client):
    seed_boss_context(client)
    session = unwrap(client.post("/api/chat/sessions", json={"title": "老板回复"}))

    with client.stream("POST", f"/api/chat/sessions/{session['session_id']}/messages", json={"content": "老板说我最近加班比较多啊"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: context" in body
    assert '"name":"老板"' in body
    assert "event: done" in body

    detail = unwrap(client.get(f"/api/chat/sessions/{session['session_id']}"))
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["context_used"]["people"][0]["name"] == "老板"
    assert "未配置可用模型" in detail["messages"][1]["content"]


def test_chat_sessions_list_and_end(client):
    session = unwrap(client.post("/api/chat/sessions", json={"title": "测试会话"}))

    sessions = unwrap(client.get("/api/chat/sessions"))
    assert sessions["items"][0]["id"] == session["session_id"]

    ended = unwrap(client.post(f"/api/chat/sessions/{session['session_id']}/end"))
    assert ended["id"] == session["session_id"]
    assert ended["ended_at"] is not None
