from tests.conftest import H

def test_member_can_read(client):
    assert client.get("/projects/1/state", headers=H(3)).status_code == 200

def test_non_member_forbidden(client):
    assert client.get("/projects/1/state", headers=H(4)).status_code == 403

def test_unknown_user_unauthorized(client):
    assert client.get("/projects/1/state", headers=H(99)).status_code == 401

def test_viewer_cannot_write(client):
    r = client.post("/projects/1/tasks", json={"title": "x"}, headers=H(3))
    assert r.status_code == 403