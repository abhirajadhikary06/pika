"""Authentication tests."""


def test_register_success(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "securepass1",
        "full_name": "New User",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["email"] == "new@example.com"
    assert "password_hash" not in data


def test_register_duplicate_email(client):
    client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "password123",
        "full_name": "User",
    })
    resp = client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "password123",
        "full_name": "User 2",
    })
    assert resp.status_code == 409


def test_login_success(client):
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "password123",
        "full_name": "Login User",
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid(client):
    resp = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_success(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": auth_headers["Authorization"]})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["email"] == "test@example.com"
