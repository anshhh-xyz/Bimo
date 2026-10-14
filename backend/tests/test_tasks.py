from tests.conftest import H

def test_create_and_update_bumps_version(client):
    t = client.post("/projects/1/tasks", json={"title": "Write schema"}, headers=H(2)).json()
    assert t["version"] == 1 and t["provenance"] == "asserted"
    r = client.patch(f"/projects/1/tasks/{t['id']}",
                     json={"version": 1, "state": "done"}, headers=H(2))
    assert r.status_code == 200 and r.json()["version"] == 2

def test_stale_write_returns_409(client):
    t = client.post("/projects/1/tasks", json={"title": "Shared task"}, headers=H(1)).json()
    url = f"/projects/1/tasks/{t['id']}"
    assert client.patch(url, json={"version": 1, "title": "A"}, headers=H(1)).status_code == 200
    r = client.patch(url, json={"version": 1, "title": "B"}, headers=H(2))
    assert r.status_code == 409
    assert r.json()["current"]["version"] == 2
    assert r.json()["current"]["title"] == "A"
    types = [e["type"] for e in client.get("/projects/1/changes", headers=H(1)).json()]
    assert "conflict_rejected" in types