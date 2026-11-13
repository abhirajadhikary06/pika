"""Ticket workflow tests."""


def test_create_and_list_tickets(client, auth_headers, workspace):
    headers = {"Authorization": auth_headers["Authorization"]}
    ws_id = workspace["id"]

    # Create
    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/tickets",
        json={"title": "Cannot login", "priority": "high", "type": "incident"},
        headers=headers,
    )
    assert resp.status_code == 201
    ticket = resp.get_json()["data"]
    assert ticket["number"] == 1
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"

    # List
    resp = client.get(f"/api/v1/workspaces/{ws_id}/tickets", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["meta"]["total"] == 1
    assert len(data["data"]) == 1


def test_ticket_isolation(client, auth_headers, workspace):
    """User without membership cannot access tickets."""
    headers = {"Authorization": auth_headers["Authorization"]}
    ws_id = workspace["id"]

    # Create another user
    client.post("/api/v1/auth/register", json={
        "email": "other@example.com",
        "password": "password123",
        "full_name": "Other",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "other@example.com",
        "password": "password123",
    })
    other_token = login.get_json()["data"]["access_token"]

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/tickets",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_add_comment(client, auth_headers, workspace):
    headers = {"Authorization": auth_headers["Authorization"]}
    ws_id = workspace["id"]

    create = client.post(
        f"/api/v1/workspaces/{ws_id}/tickets",
        json={"title": "Test ticket"},
        headers=headers,
    )
    ticket_id = create.get_json()["data"]["id"]

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/tickets/{ticket_id}/comments",
        json={"body": "Looking into this."},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["body"] == "Looking into this."
    assert resp.get_json()["data"]["is_internal"] is False


def test_workspace_stats(client, auth_headers, workspace):
    headers = {"Authorization": auth_headers["Authorization"]}
    ws_id = workspace["id"]

    client.post(
        f"/api/v1/workspaces/{ws_id}/tickets",
        json={"title": "T1", "priority": "urgent"},
        headers=headers,
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/tickets",
        json={"title": "T2", "priority": "low"},
        headers=headers,
    )

    resp = client.get(f"/api/v1/workspaces/{ws_id}/stats", headers=headers)
    assert resp.status_code == 200
    stats = resp.get_json()["data"]
    assert stats["total"] == 2
    assert stats["open"] == 2
