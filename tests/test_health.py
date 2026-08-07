"""
Tests for GET /health (api/routes/health.py). Covers the DynamoDB liveness
check specifically — this route used to hard-ping Mongo and had no test
coverage for either backend, so a DynamoDB-unreachable case is added here
alongside the plain healthy case.
"""

from fastapi.testclient import TestClient

from api.main import app
import api.routes.health as health

client = TestClient(app)


def test_health_reports_healthy_when_dynamodb_reachable():
    resp = client.get("/health")
    assert resp.json()["dependencies"]["dynamodb"] == "healthy"


def test_health_reports_unhealthy_when_dynamodb_unreachable(monkeypatch):
    def _boom():
        raise RuntimeError("could not connect")

    monkeypatch.setattr(health, "get_exercises_table", _boom)
    resp = client.get("/health")
    body = resp.json()
    assert resp.status_code == 503
    assert body["status"] == "unhealthy"
    assert body["dependencies"]["dynamodb"] == "unhealthy: could not connect"
