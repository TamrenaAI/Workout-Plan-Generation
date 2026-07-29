"""
Tests for /auth/dev-login endpoint.
"""

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_dev_login_returns_valid_token():
    response = client.post("/auth/dev-login")
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user_id"] == "65f1a2b3c4d5e6f7a8b9c0d1"
    assert len(data["token"]) > 20
