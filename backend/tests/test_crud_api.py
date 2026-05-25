def unwrap(response):
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"] is True
    return body["data"]


def assert_error(response, status_code, message):
    assert response.status_code == status_code
    assert response.json() == {"ok": False, "error": message}


def test_people_crud_and_search(client):
    created = unwrap(
        client.post(
            "/api/people",
            json={
                "name": "张三",
                "aliases": ["小张", "张总"],
                "bio": "前同事",
                "importance": 3,
            },
        )
    )
    person_id = created["id"]
    assert created["name"] == "张三"
    assert created["aliases"] == ["小张", "张总"]

    listed = unwrap(client.get("/api/people", params={"q": "张总"}))
    assert [person["id"] for person in listed["items"]] == [person_id]

    detail = unwrap(client.get(f"/api/people/{person_id}"))
    assert detail["person"]["bio"] == "前同事"
    assert detail["relationships"] == []
    assert detail["events"] == []
    assert detail["notes"] == []
    assert detail["stages"] == []

    updated = unwrap(client.patch(f"/api/people/{person_id}", json={"importance": 5}))
    assert updated["importance"] == 5

    search = unwrap(client.get("/api/search", params={"q": "前同事"}))
    assert search["people"][0]["id"] == person_id

    deleted = unwrap(client.delete(f"/api/people/{person_id}"))
    assert deleted == {"id": person_id}
    assert_error(client.get(f"/api/people/{person_id}"), 404, "person not found")


def test_entities_members_crud(client):
    person = unwrap(client.post("/api/people", json={"name": "李四"}))
    entity = unwrap(client.post("/api/entities", json={"type": "company", "name": "字节跳动"}))
    listed = unwrap(client.get("/api/entities", params={"q": "字节"}))
    assert [item["id"] for item in listed["items"]] == [entity["id"]]

    member = unwrap(
        client.post(
            f"/api/entities/{entity['id']}/members",
            json={"person_id": person["id"], "role": "同事"},
        )
    )
    assert member["person_id"] == person["id"]
    assert member["role"] == "同事"

    detail = unwrap(client.get(f"/api/entities/{entity['id']}"))
    assert detail["entity"]["name"] == "字节跳动"
    assert detail["members"][0]["person"]["name"] == "李四"

    updated = unwrap(client.patch(f"/api/entities/{entity['id']}", json={"bio": "工作单位"}))
    assert updated["bio"] == "工作单位"

    removed = unwrap(client.delete(f"/api/entities/{entity['id']}/members/{person['id']}"))
    assert removed == {"entity_id": entity["id"], "person_id": person["id"]}
    assert unwrap(client.get(f"/api/entities/{entity['id']}"))["members"] == []

    deleted = unwrap(client.delete(f"/api/entities/{entity['id']}"))
    assert deleted == {"id": entity["id"]}


def test_relationships_events_stages_and_self_crud(client):
    person = unwrap(client.post("/api/people", json={"name": "王五"}))

    self_profile = unwrap(
        client.patch(
            "/api/self",
            json={
                "name": "我",
                "bio": "自用用户",
                "communication_style": "直接",
                "sensitivities": ["被催"],
                "goals": ["减少误解"],
            },
        )
    )
    assert self_profile["name"] == "我"
    assert unwrap(client.get("/api/self"))["communication_style"] == "直接"

    stage = unwrap(
        client.post(
            "/api/stages",
            json={"name": "大学", "kind": "教育", "started_at": "2018-09-01", "sort_order": 1},
        )
    )
    assert stage["name"] == "大学"
    assert unwrap(client.patch(f"/api/stages/{stage['id']}", json={"location": "北京"}))["location"] == "北京"
    assert unwrap(client.get("/api/stages"))["items"][0]["id"] == stage["id"]

    relationship = unwrap(
        client.post(
            "/api/relationships",
            json={
                "from_type": "self",
                "to_type": "person",
                "to_id": person["id"],
                "relation_type": "朋友",
                "role": "大学同学",
                "strength": 4,
            },
        )
    )
    assert relationship["relation_type"] == "朋友"
    assert unwrap(client.patch(f"/api/relationships/{relationship['id']}", json={"status": "活跃"}))["status"] == "活跃"
    assert unwrap(client.get("/api/relationships", params={"to": f"person:{person['id']}"}))["items"][0]["id"] == relationship["id"]
    assert unwrap(client.get("/api/relationships", params={"from": "self"}))["items"][0]["id"] == relationship["id"]

    event = unwrap(
        client.post(
            "/api/events",
            json={
                "occurred_at": "2026-05-23",
                "title": "一起吃饭",
                "participants": [{"type": "person", "id": person["id"]}],
                "source": "manual",
            },
        )
    )
    assert event["title"] == "一起吃饭"
    assert unwrap(client.get("/api/events", params={"person_id": person["id"]}))["items"][0]["id"] == event["id"]
    assert unwrap(client.patch(f"/api/events/{event['id']}", json={"importance": 2}))["importance"] == 2

    assert unwrap(client.delete(f"/api/events/{event['id']}")) == {"id": event["id"]}
    assert unwrap(client.delete(f"/api/relationships/{relationship['id']}")) == {"id": relationship["id"]}
    assert unwrap(client.delete(f"/api/stages/{stage['id']}")) == {"id": stage["id"]}


def test_person_stage_assignment(client):
    person = unwrap(client.post("/api/people", json={"name": "大学同学"}))
    stage = unwrap(client.post("/api/stages", json={"name": "大学", "kind": "教育"}))

    assignment = unwrap(
        client.post(
            f"/api/people/{person['id']}/stages",
            json={"stage_id": stage["id"], "role_in_stage": "同班同学", "started_at": "2018-09-01"},
        )
    )

    assert assignment["person_id"] == person["id"]
    assert assignment["stage_id"] == stage["id"]
    assert assignment["role_in_stage"] == "同班同学"

    detail = unwrap(client.get(f"/api/people/{person['id']}"))
    assert detail["stages"][0]["stage"]["name"] == "大学"
    assert detail["stages"][0]["role_in_stage"] == "同班同学"

    removed = unwrap(client.delete(f"/api/people/{person['id']}/stages/{stage['id']}"))
    assert removed == {"person_id": person["id"], "stage_id": stage["id"]}
    assert unwrap(client.get(f"/api/people/{person['id']}"))["stages"] == []


def test_person_merge_updates_relationship_targets(client):
    target = unwrap(client.post("/api/people", json={"name": "老板"}))
    source = unwrap(client.post("/api/people", json={"name": "张总"}))
    relationship = unwrap(
        client.post(
            "/api/relationships",
            json={
                "from_type": "self",
                "to_type": "person",
                "to_id": source["id"],
                "relation_type": "上下级",
                "role": "老板",
            },
        )
    )

    result = unwrap(client.post(f"/api/people/{source['id']}/merge", json={"target_person_id": target["id"]}))
    assert result == {"source_id": source["id"], "target_id": target["id"]}
    assert_error(client.get(f"/api/people/{source['id']}"), 404, "person not found")

    moved = unwrap(client.get(f"/api/relationships/{relationship['id']}"))
    assert moved["to_id"] == target["id"]


def test_person_photo_upload(client):
    person = unwrap(client.post("/api/people", json={"name": "赵六"}))

    uploaded = unwrap(
        client.post(
            f"/api/people/{person['id']}/photo",
            files={"file": ("avatar.jpg", b"fake-jpeg", "image/jpeg")},
        )
    )

    assert uploaded["photo_path"].startswith("/api/files/photos/")
    detail = unwrap(client.get(f"/api/people/{person['id']}"))
    assert detail["person"]["photo_path"] == uploaded["photo_path"]
    photo = client.get(uploaded["photo_path"])
    assert photo.status_code == 200
    assert photo.content == b"fake-jpeg"
