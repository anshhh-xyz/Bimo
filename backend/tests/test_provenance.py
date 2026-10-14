from tests.conftest import H

def test_client_cannot_set_verified(client):
    r = client.post("/projects/1/tasks",
                    json={"title": "x", "provenance": "verified"}, headers=H(2))
    assert r.status_code == 422

def test_decision_defaults_to_asserted_and_shows_in_unverified(client):
    d = client.post("/projects/1/decisions",
                    json={"topic": "db", "decision": "Use Postgres"}, headers=H(1)).json()
    assert d["provenance"] == "asserted" and d["surface"] == "code"
    state = client.get("/projects/1/state", headers=H(3)).json()
    assert any(u["kind"] == "decision" and u["id"] == d["id"] for u in state["unverified"])