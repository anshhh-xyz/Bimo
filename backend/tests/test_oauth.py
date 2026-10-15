import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest

from app.services import oauth

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("USER_PASSPHRASES", "user1@test.dev:pw1")
    monkeypatch.setenv("PUBLIC_URL", "https://example.test")


def pkce():
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def register(client):
    r = client.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "t"})
    assert r.status_code == 201
    return r.json()["client_id"]


def get_code(client, client_id, challenge, passphrase="pw1"):
    return client.post("/authorize", follow_redirects=False, data={
        "client_id": client_id, "redirect_uri": REDIRECT, "state": "xyz",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "email": "user1@test.dev", "passphrase": passphrase})


def token_request(client, client_id, code, verifier):
    return client.post("/token", data={
        "grant_type": "authorization_code", "client_id": client_id, "code": code,
        "redirect_uri": REDIRECT, "code_verifier": verifier})


def test_discovery_documents(client):
    meta = client.get("/.well-known/oauth-authorization-server").json()
    assert meta["registration_endpoint"] == "https://example.test/register"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    res = client.get("/.well-known/oauth-protected-resource").json()
    assert res["authorization_servers"] == ["https://example.test"]


def test_register_rejects_foreign_redirect(client):
    r = client.post("/register", json={"redirect_uris": ["https://evil.example/cb"]})
    assert r.status_code == 400 and r.json()["error"] == "invalid_client_metadata"


def test_full_flow_gives_a_working_token_for_the_right_user(client, session):
    client_id = register(client)
    verifier, challenge = pkce()
    page = client.get("/authorize", params={
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
        "state": "xyz", "code_challenge": challenge, "code_challenge_method": "S256"})
    assert page.status_code == 200 and "Authorize" in page.text

    r = get_code(client, client_id, challenge)
    assert r.status_code == 302
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert q["state"] == ["xyz"]

    t = token_request(client, client_id, q["code"][0], verifier)
    assert t.status_code == 200
    body = t.json()
    assert oauth.user_for_access_token(session, body["access_token"]) == 1

    # refresh rotates: new token works, old refresh token is dead
    r2 = client.post("/token", data={"grant_type": "refresh_token",
                                     "client_id": client_id,
                                     "refresh_token": body["refresh_token"]})
    assert r2.status_code == 200
    again = client.post("/token", data={"grant_type": "refresh_token",
                                        "client_id": client_id,
                                        "refresh_token": body["refresh_token"]})
    assert again.status_code == 400


def test_wrong_passphrase_gets_no_code(client):
    client_id = register(client)
    _, challenge = pkce()
    assert get_code(client, client_id, challenge, passphrase="nope").status_code == 401


def test_wrong_verifier_and_code_reuse_fail(client):
    client_id = register(client)
    verifier, challenge = pkce()
    code = parse_qs(urlsplit(get_code(client, client_id, challenge)
                             .headers["location"]).query)["code"][0]
    assert token_request(client, client_id, code, "wrong-verifier-" * 4).status_code == 400
    # the failed attempt burned the code, so even the right verifier now fails
    assert token_request(client, client_id, code, verifier).status_code == 400


def test_unregistered_redirect_is_not_followed(client):
    client_id = register(client)
    _, challenge = pkce()
    r = client.get("/authorize", params={
        "client_id": client_id, "redirect_uri": "https://evil.example/cb",
        "code_challenge": challenge, "code_challenge_method": "S256"})
    assert r.status_code == 400


def test_public_guard_hides_rest_but_not_health(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_MODE", "1")
    assert client.get("/health").status_code == 200
    assert client.get("/projects/1/state",
                      headers={"X-User-Id": "1", "X-Surface": "web"}).status_code == 404
    monkeypatch.setenv("PUBLIC_MODE", "0")
    assert client.get("/projects/1/state",
                      headers={"X-User-Id": "1", "X-Surface": "web"}).status_code == 200