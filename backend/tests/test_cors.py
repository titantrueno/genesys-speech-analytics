from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def preflight(origin):
    return client.options("/api/auth/me", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })


def test_frontend_dev_origin_is_allowed():
    response = preflight("http://localhost:5173")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_unknown_origin_is_rejected():
    response = preflight("https://malicioso.example")
    assert "access-control-allow-origin" not in response.headers
