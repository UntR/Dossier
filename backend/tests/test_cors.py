def test_frontend_origin_can_call_api(client):
    response = client.options(
        "/api/people",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_random_local_frontend_port_can_call_api(client):
    response = client.options(
        "/api/people",
        headers={
            "Origin": "http://127.0.0.1:45262",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:45262"
