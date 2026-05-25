def test_validation_errors_use_api_envelope(client):
    response = client.post("/api/people", json={"bio": "missing name"})

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "name" in body["error"]


def test_phase2_request_bodies_are_named_pydantic_schemas(client):
    openapi = client.get("/openapi.json").json()
    schemas = openapi["components"]["schemas"]

    expected = {
        "PersonCreate",
        "PersonUpdate",
        "PersonMergeRequest",
        "EntityCreate",
        "EntityUpdate",
        "EntityMemberCreate",
        "RelationshipCreate",
        "RelationshipUpdate",
        "EventCreate",
        "EventUpdate",
        "LifeStageCreate",
        "LifeStageUpdate",
        "PersonStageCreate",
        "SelfProfileUpdate",
    }
    assert expected.issubset(schemas.keys())

    person_body = openapi["paths"]["/api/people"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert person_body["$ref"].endswith("/PersonCreate")
    relationship_body = openapi["paths"]["/api/relationships"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert relationship_body["$ref"].endswith("/RelationshipCreate")


def test_relationship_strength_validation(client):
    person = client.post("/api/people", json={"name": "老板"}).json()["data"]

    response = client.post(
        "/api/relationships",
        json={
            "from_type": "self",
            "to_type": "person",
            "to_id": person["id"],
            "relation_type": "上下级",
            "strength": 8,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "strength" in body["error"]
