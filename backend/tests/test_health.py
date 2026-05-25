from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_cors_origins_can_include_lan_frontend(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://192.168.0.229:25185")
    client = TestClient(create_app())

    response = client.options(
        "/health",
        headers={
            "Origin": "http://192.168.0.229:25185",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.0.229:25185"
