from fastapi.testclient import TestClient

from rozmarra.api.main import app

client = TestClient(app)


def test_health_endpoint_reports_that_the_service_is_running():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "Rozmarra API"
    assert set(body) == {"status", "service", "version", "message"}


def test_dashboard_origin_is_allowed():
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
