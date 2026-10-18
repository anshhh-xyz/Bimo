import pytest
from app.models import Project, ProjectMember
from tests.conftest import H

URL = "/projects/1/members"


def test_member_can_list(client):
    r = client.get(URL, headers=H(3))
    assert r.status_code == 200
    by_email = {m["email"]: m["role"] for m in r.json()}
    assert by_email == {"user1@test.dev": "owner",
                        "user2@test.dev": "editor",
                        "user3@test.dev": "viewer"}


def test_non_member_cannot_list(client):
    assert client.get(URL, headers=H(4)).status_code == 403


def test_owner_adds_member_and_access_is_granted(client):
    assert client.get("/projects/1/state", headers=H(4)).status_code == 403
    r = client.post(URL, json={"email": "USER4@test.dev", "role": "viewer"},
                    headers=H(1))
    assert r.status_code == 201
    assert r.json()["email"] == "user4@test.dev" and r.json()["role"] == "viewer"
    assert client.get("/projects/1/state", headers=H(4)).status_code == 200
    # viewer role is read-only
    assert client.post("/projects/1/tasks", json={"title": "x"},
                       headers=H(4)).status_code == 403


def test_add_unknown_email_is_404(client):
    r = client.post(URL, json={"email": "nobody@test.dev"}, headers=H(1))
    assert r.status_code == 404


def test_add_duplicate_is_409(client):
    r = client.post(URL, json={"email": "user2@test.dev"}, headers=H(1))
    assert r.status_code == 409


def test_invalid_role_is_422(client):
    r = client.post(URL, json={"email": "user4@test.dev", "role": "admin"},
                    headers=H(1))
    assert r.status_code == 422


@pytest.mark.parametrize("uid", [2, 3])  # editor and viewer
def test_non_owner_cannot_manage(client, uid):
    assert client.post(URL, json={"email": "user4@test.dev"},
                       headers=H(uid)).status_code == 403
    assert client.patch(f"{URL}/3", json={"role": "owner"},
                        headers=H(uid)).status_code == 403
    assert client.delete(f"{URL}/2", headers=H(uid)).status_code == 403


def test_role_change_takes_effect_immediately(client):
    assert client.post("/projects/1/tasks", json={"title": "x"},
                       headers=H(3)).status_code == 403
    r = client.patch(f"{URL}/3", json={"role": "editor"}, headers=H(1))
    assert r.status_code == 200 and r.json()["role"] == "editor"
    assert client.post("/projects/1/tasks", json={"title": "x"},
                       headers=H(3)).status_code == 201
    client.patch(f"{URL}/3", json={"role": "viewer"}, headers=H(1))
    assert client.post("/projects/1/tasks", json={"title": "y"},
                       headers=H(3)).status_code == 403


def test_patch_non_member_is_404(client):
    assert client.patch(f"{URL}/4", json={"role": "viewer"},
                        headers=H(1)).status_code == 404


def test_removed_member_loses_access(client):
    assert client.get("/projects/1/state", headers=H(3)).status_code == 200
    assert client.delete(f"{URL}/3", headers=H(1)).status_code == 204
    assert client.get("/projects/1/state", headers=H(3)).status_code == 403


def test_cannot_demote_or_remove_last_owner(client):
    assert client.patch(f"{URL}/1", json={"role": "viewer"},
                        headers=H(1)).status_code == 409
    assert client.delete(f"{URL}/1", headers=H(1)).status_code == 409


def test_owner_can_leave_if_another_owner_exists(client):
    client.patch(f"{URL}/2", json={"role": "owner"}, headers=H(1))
    assert client.delete(f"{URL}/1", headers=H(1)).status_code == 204
    assert client.get("/projects/1/state", headers=H(1)).status_code == 403
    assert client.get("/projects/1/state", headers=H(2)).status_code == 200


def test_membership_changes_are_logged(client):
    client.post(URL, json={"email": "user4@test.dev"}, headers=H(1))
    client.delete(f"{URL}/4", headers=H(1))
    types = [e["type"] for e in client.get("/projects/1/changes",
                                           headers=H(1)).json()]
    assert "member_added" in types and "member_removed" in types


def test_owner_of_another_project_has_no_power_here(client, session):
    session.add(Project(id=2, name="other"))
    session.flush()
    session.add(ProjectMember(project_id=2, user_id=4, role="owner"))
    session.commit()
    assert client.get("/projects/2/state", headers=H(4)).status_code == 200
    assert client.get("/projects/1/state", headers=H(4)).status_code == 403
    assert client.post(URL, json={"email": "user4@test.dev"},
                       headers=H(4)).status_code == 403


# 4.9 guard: every project route must reject a non-member
ROUTES = [
    ("get", "/projects/1/state", None),
    ("get", "/projects/1/changes", None),
    ("get", "/projects/1/handoffs/latest", None),
    ("post", "/projects/1/tasks", {"title": "x"}),
    ("patch", "/projects/1/tasks/1", {"version": 1, "title": "x"}),
    ("post", "/projects/1/decisions", {"topic": "t", "decision": "d"}),
    ("post", "/projects/1/handoffs", {"summary": "s"}),
    ("get", "/projects/1/members", None),
    ("post", "/projects/1/members", {"email": "user4@test.dev"}),
    ("patch", "/projects/1/members/3", {"role": "viewer"}),
    ("delete", "/projects/1/members/3", None),
]


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_every_project_route_rejects_non_member(client, method, path, body):
    r = client.request(method, path, json=body, headers=H(4))
    assert r.status_code == 403