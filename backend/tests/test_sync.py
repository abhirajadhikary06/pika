"""Regression tests for offline sync endpoints and authorization."""
import uuid

from app import db
from app.models.workspace import Membership
from app.models.user import User


def _ticket(client, auth_headers, workspace):
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets",
        json={"title": "Sync test ticket"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_sync_create_is_idempotent(client, auth_headers, workspace):
    headers = {"Authorization": auth_headers["Authorization"]}
    operation = {
        "op_id": str(uuid.uuid4()),
        "record_type": "ticket",
        "operation": "create",
        "payload": {"id": str(uuid.uuid4()), "title": "Created offline", "priority": "high"},
    }
    endpoint = f"/api/v1/workspaces/{workspace['id']}/sync/push"

    first = client.post(endpoint, json={"operations": [operation]}, headers=headers)
    second = client.post(endpoint, json={"operations": [operation]}, headers=headers)

    assert first.status_code == second.status_code == 200
    first_result = first.get_json()["data"]["results"][0]
    second_result = second.get_json()["data"]["results"][0]
    assert first_result["status"] == second_result["status"] == "synced"
    assert first_result["result"]["id"] == second_result["result"]["id"]
    listed = client.get(f"/api/v1/workspaces/{workspace['id']}/tickets", headers=headers)
    assert listed.get_json()["meta"]["total"] == 1


def test_sync_update_reports_stale_base_version(client, auth_headers, workspace):
    ticket = _ticket(client, auth_headers, workspace)
    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/sync/push",
        json={"operations": [{
            "op_id": str(uuid.uuid4()),
            "record_type": "ticket",
            "operation": "update",
            "base_version": 0,
            "payload": {"id": ticket["id"], "changes": {"status": "closed"}},
        }]},
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    conflict = response.get_json()["data"]["results"][0]
    assert conflict["status"] == "conflict"
    assert conflict["server"]["version"] == ticket["version"]
    assert conflict["server"]["status"] == "open"


def test_sync_pull_pages_changes_and_returns_delete_tombstones(client, auth_headers, workspace):
    headers = {"Authorization": auth_headers["Authorization"]}
    ticket = _ticket(client, auth_headers, workspace)
    first_page = client.get(
        f"/api/v1/workspaces/{workspace['id']}/sync/pull?cursor=0&limit=1", headers=headers,
    ).get_json()["data"]
    assert len(first_page["changes"]) == 1
    assert first_page["has_more"] is True

    removed = client.post(
        f"/api/v1/workspaces/{workspace['id']}/sync/push",
        json={"operations": [{
            "op_id": str(uuid.uuid4()),
            "record_type": "ticket",
            "operation": "delete",
            "base_version": ticket["version"],
            "payload": {"id": ticket["id"]},
        }]},
        headers=headers,
    )
    assert removed.status_code == 200
    assert removed.get_json()["data"]["results"][0]["status"] == "synced"
    remaining = client.get(
        f"/api/v1/workspaces/{workspace['id']}/sync/pull?cursor={first_page['cursor']}&limit=100",
        headers=headers,
    ).get_json()["data"]
    assert any(change["operation"] == "delete" and change["entity_id"] == ticket["id"]
               for change in remaining["changes"])


def test_sync_pull_hides_internal_notes_from_viewers(client, auth_headers, workspace, app):
    ticket = _ticket(client, auth_headers, workspace)
    owner_headers = {"Authorization": auth_headers["Authorization"]}
    comment = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets/{ticket['id']}/comments",
        json={"body": "private sync note", "is_internal": True},
        headers=owner_headers,
    )
    assert comment.status_code == 201

    with app.app_context():
        client.post("/api/v1/auth/register", json={
            "email": "sync-viewer@example.com",
            "password": "password123",
            "full_name": "Sync Viewer",
        })
        login = client.post("/api/v1/auth/login", json={
            "email": "sync-viewer@example.com",
            "password": "password123",
        })
        viewer = User.query.filter_by(email="sync-viewer@example.com").first()
        db.session.add(Membership(
            workspace_id=uuid.UUID(workspace["id"]), user_id=viewer.id, role="viewer", is_active=True,
        ))
        db.session.commit()
        viewer_headers = {"Authorization": f"Bearer {login.get_json()['data']['access_token']}"}

    endpoint = f"/api/v1/workspaces/{workspace['id']}/sync/pull?cursor=0"
    viewer_response = client.get(endpoint, headers=viewer_headers)
    owner_response = client.get(endpoint, headers=owner_headers)
    assert viewer_response.status_code == owner_response.status_code == 200
    viewer_changes = viewer_response.get_json()["data"]["changes"]
    owner_changes = owner_response.get_json()["data"]["changes"]
    assert "private sync note" not in str(viewer_changes)
    assert any(change["entity_type"] == "comment" for change in owner_changes)
    assert viewer_response.get_json()["data"]["cursor"] == owner_response.get_json()["data"]["cursor"]
