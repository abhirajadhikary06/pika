"""Pytest fixtures."""
import pytest
from app import create_app, db
from app.models.user import User
from app.models.workspace import Workspace, Membership


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """Register and login a user, return Authorization header + user data."""
    reg = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User",
    })
    assert reg.status_code == 201

    login = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert login.status_code == 200
    data = login.get_json()["data"]
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "user": data["user"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }


@pytest.fixture
def workspace(client, auth_headers):
    resp = client.post(
        "/api/v1/workspaces",
        json={"name": "Test Workspace", "slug": "test-ws"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]
