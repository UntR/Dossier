from test_crud_api import unwrap


def seed_timeline(client):
    unwrap(client.patch("/api/self", json={"name": "我"}))
    coworker = unwrap(client.post("/api/people", json={"name": "同事甲"}))
    boss = unwrap(client.post("/api/people", json={"name": "老板乙"}))
    university = unwrap(client.post("/api/stages", json={"name": "大学", "kind": "教育", "started_at": "2018-09-01", "ended_at": "2022-06-30", "sort_order": 1}))
    work = unwrap(client.post("/api/stages", json={"name": "工作", "kind": "工作", "started_at": "2022-07-01", "sort_order": 2}))
    unwrap(client.post(f"/api/people/{coworker['id']}/stages", json={"stage_id": university["id"], "role_in_stage": "同学", "started_at": "2019-01-01"}))
    unwrap(client.post(f"/api/people/{boss['id']}/stages", json={"stage_id": work["id"], "role_in_stage": "直属上级", "started_at": "2023-01-01"}))
    unwrap(client.post("/api/relationships", json={"from_type": "self", "to_type": "person", "to_id": coworker["id"], "relation_type": "朋友", "role": "同学"}))
    unwrap(client.post("/api/relationships", json={"from_type": "self", "to_type": "person", "to_id": boss["id"], "relation_type": "上下级", "role": "老板"}))
    unwrap(client.post("/api/events", json={"occurred_at": "2020-05-20", "title": "一起做课程项目", "participants": [{"type": "person", "id": coworker["id"]}], "source": "manual"}))
    unwrap(client.post("/api/events", json={"occurred_at": "2024-03-10", "title": "周会被提醒进度", "participants": [{"type": "person", "id": boss["id"]}], "source": "manual"}))
    return {"coworker": coworker, "boss": boss, "university": university, "work": work}


def test_timeline_groups_people_and_events_by_stage(client):
    data = seed_timeline(client)

    timeline = unwrap(client.get("/api/timeline"))

    assert timeline["self"]["name"] == "我"
    assert [stage["name"] for stage in timeline["stages"]] == ["大学", "工作"]
    university, work = timeline["stages"]
    assert university["people"][0]["person_id"] == data["coworker"]["id"]
    assert university["people"][0]["role_in_stage"] == "同学"
    assert university["events"][0]["title"] == "一起做课程项目"
    assert work["people"][0]["person_id"] == data["boss"]["id"]
    assert work["events"][0]["title"] == "周会被提醒进度"


def test_timeline_filters_stage_and_relation_type(client):
    data = seed_timeline(client)

    stage_filtered = unwrap(client.get("/api/timeline", params={"stage_id": data["work"]["id"]}))
    assert [stage["name"] for stage in stage_filtered["stages"]] == ["工作"]

    relation_filtered = unwrap(client.get("/api/timeline", params={"relation_type": "上下级"}))
    assert [stage["name"] for stage in relation_filtered["stages"]] == ["工作"]
    assert relation_filtered["stages"][0]["people"][0]["name"] == "老板乙"
    assert relation_filtered["stages"][0]["events"][0]["title"] == "周会被提醒进度"
