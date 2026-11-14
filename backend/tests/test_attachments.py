"""Attachment authorization and online transfer tests."""
import io
import uuid

from app import db
from app.models.user import User
from app.models.workspace import Membership


def test_attachment_upload_and_download_are_online_and_authorized(client, auth_headers, workspace, app, tmp_path):
    headers = {"Authorization": auth_headers["Authorization"]}
    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets",
        json={"title": "Attachment ticket"},
        headers=headers,
    )
    ticket_id = created.get_json()["data"]["id"]
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    app.config["USE_OBJECT_STORAGE"] = False

    uploaded = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets/{ticket_id}/attachments",
        data={"file": (io.BytesIO(b"attachment contents"), "notes.txt")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert uploaded.status_code == 201
    attachment = uploaded.get_json()["data"]
    downloaded = client.get(
        f"/api/v1/workspaces/{workspace['id']}/tickets/{ticket_id}/attachments/{attachment['id']}",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.data == b"attachment contents"


def test_viewer_cannot_upload_attachment(client, auth_headers, workspace, app):
    headers = {"Authorization": auth_headers["Authorization"]}
    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets",
        json={"title": "Viewer attachment check"},
        headers=headers,
    )
    ticket_id = created.get_json()["data"]["id"]

    client.post("/api/v1/auth/register", json={
        "email": "attachment-viewer@example.com",
        "password": "password123",
        "full_name": "Attachment Viewer",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "attachment-viewer@example.com",
        "password": "password123",
    })
    viewer = User.query.filter_by(email="attachment-viewer@example.com").first()
    db.session.add(Membership(
        workspace_id=uuid.UUID(workspace["id"]), user_id=viewer.id, role="viewer", is_active=True,
    ))
    db.session.commit()
    viewer_headers = {"Authorization": f"Bearer {login.get_json()['data']['access_token']}"}

    response = client.post(
        f"/api/v1/workspaces/{workspace['id']}/tickets/{ticket_id}/attachments",
        data={"file": (io.BytesIO(b"not allowed"), "notes.txt")},
        content_type="multipart/form-data",
        headers=viewer_headers,
    )
    assert response.status_code == 403
