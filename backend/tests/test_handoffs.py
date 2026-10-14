from tests.conftest import H


def test_handoff_round_trip(client):
    body = {"summary": "Phase 2 half done", "completed": ["auth"],
            "blockers": [], "open_questions": ["role model?"],
            "files_touched": ["app/auth.py"], "last_commit_sha": "abc123",
            "verification_status": "unverified",
            "next_action": "write handoff tests"}
    r = client.post("/projects/1/handoffs", json=body, headers=H(2, "web"))
    assert r.status_code == 201
    latest = client.get("/projects/1/handoffs/latest", headers=H(1)).json()
    assert latest["next_action"] == "write handoff tests"
    assert latest["surface"] == "web"
    state = client.get("/projects/1/state", headers=H(3)).json()
    assert state["latest_handoff"]["id"] == latest["id"]


def test_no_handoff_yet_is_404(client):
    assert client.get("/projects/1/handoffs/latest", headers=H(1)).status_code == 404