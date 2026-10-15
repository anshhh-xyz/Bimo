import html
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Body, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import public_url
from app.db import get_session
from app.models import OAuthClient
from app.services import oauth as svc

router = APIRouter(tags=["oauth"])


def _base(request: Request) -> str:
    return public_url() or str(request.base_url).rstrip("/")


def _err(e: svc.OAuthError, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": e.error, "error_description": e.description},
                        status_code=status, headers={"Cache-Control": "no-store"})


# ---------- discovery: how Claude finds out where to log in ----------
def _protected_resource(request: Request):
    base = _base(request)
    return {"resource": f"{base}/mcp", "authorization_servers": [base],
            "bearer_methods_supported": ["header"]}


@router.get("/.well-known/oauth-protected-resource")
def protected_resource(request: Request):
    return _protected_resource(request)


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_mcp(request: Request):
    return _protected_resource(request)


@router.get("/.well-known/oauth-authorization-server")
def authorization_server(request: Request):
    base = _base(request)
    return {"issuer": base,
            "authorization_endpoint": f"{base}/authorize",
            "token_endpoint": f"{base}/token",
            "registration_endpoint": f"{base}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"]}


# ---------- dynamic client registration ----------
@router.post("/register")
def register(body: dict = Body(...), session=Depends(get_session)):
    try:
        client = svc.register_client(session, body.get("redirect_uris"),
                                     body.get("client_name"))
    except svc.OAuthError as e:
        return _err(svc.OAuthError(
            "invalid_client_metadata" if e.error == "invalid_redirect_uri" else e.error,
            e.description))
    return JSONResponse({"client_id": client.client_id,
                         "client_name": client.client_name,
                         "redirect_uris": client.redirect_uris,
                         "grant_types": ["authorization_code", "refresh_token"],
                         "response_types": ["code"],
                         "token_endpoint_auth_method": "none"}, status_code=201)


# ---------- authorize: the login page ----------
def _page(body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>Connect</title><body style='font-family:system-ui;max-width:380px;"
        "margin:12vh auto;padding:0 16px'>" + body, status_code=status)


def _check_request(session, client_id, redirect_uri, response_type,
                   code_challenge, method) -> str | None:
    """Return an error message, or None if the request is valid.
    Errors are shown on this page and NEVER redirected, because an unverified
    redirect_uri must not be trusted."""
    client = session.get(OAuthClient, client_id)
    if client is None:
        return "Unknown client."
    if redirect_uri not in client.redirect_uris:
        return "Redirect URI does not match the registered one."
    if response_type != "code":
        return "Only response_type=code is supported."
    if method != "S256" or not (43 <= len(code_challenge) <= 128):
        return "PKCE with S256 is required."
    return None


def _form(client_id, redirect_uri, state, code_challenge, method, error="") -> str:
    hidden = "".join(
        f"<input type=hidden name={n} value=\"{html.escape(v, quote=True)}\">"
        for n, v in [("client_id", client_id), ("redirect_uri", redirect_uri),
                     ("state", state), ("code_challenge", code_challenge),
                     ("code_challenge_method", method)])
    err = f"<p style=color:#b00>{html.escape(error)}</p>" if error else ""
    return ("<h2>Connect to Project Memory</h2><p>Log in as the user this Claude "
            f"account should act as.</p>{err}<form method=post action=/authorize>{hidden}"
            "<p><input name=email type=email placeholder=Email required style=width:100%></p>"
            "<p><input name=passphrase type=password placeholder=Passphrase required "
            "style=width:100%></p><button type=submit>Authorize</button></form>")


@router.get("/authorize")
def authorize_get(client_id: str = Query(...), redirect_uri: str = Query(...),
                  response_type: str = Query("code"), state: str = Query(""),
                  code_challenge: str = Query(""),
                  code_challenge_method: str = Query(""),
                  session=Depends(get_session)):
    problem = _check_request(session, client_id, redirect_uri, response_type,
                             code_challenge, code_challenge_method)
    if problem:
        return _page(f"<h3>Cannot continue</h3><p>{html.escape(problem)}</p>", 400)
    return _page(_form(client_id, redirect_uri, state, code_challenge, code_challenge_method))


@router.post("/authorize")
def authorize_post(client_id: str = Form(...), redirect_uri: str = Form(...),
                   state: str = Form(""), code_challenge: str = Form(...),
                   code_challenge_method: str = Form(...),
                   email: str = Form(...), passphrase: str = Form(...),
                   session=Depends(get_session)):
    problem = _check_request(session, client_id, redirect_uri, "code",
                             code_challenge, code_challenge_method)
    if problem:
        return _page(f"<h3>Cannot continue</h3><p>{html.escape(problem)}</p>", 400)
    user = svc.verify_login(session, email, passphrase)
    if user is None:
        return _page(_form(client_id, redirect_uri, state, code_challenge,
                           code_challenge_method, "Wrong email or passphrase."), 401)
    code = svc.create_code(session, client_id, user.id, redirect_uri, code_challenge)
    parts = urlsplit(redirect_uri)
    query = parse_qsl(parts.query) + [("code", code)] + ([("state", state)] if state else [])
    return RedirectResponse(
        urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), "")),
        status_code=302)


# ---------- token ----------
@router.post("/token")
def token(grant_type: str = Form(...), client_id: str = Form(...),
          code: str | None = Form(None), redirect_uri: str | None = Form(None),
          code_verifier: str | None = Form(None), refresh_token: str | None = Form(None),
          session=Depends(get_session)):
    try:
        if grant_type == "authorization_code":
            if not (code and redirect_uri and code_verifier):
                raise svc.OAuthError("invalid_request", "code, redirect_uri, code_verifier required")
            result = svc.exchange_code(session, client_id, code, redirect_uri, code_verifier)
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise svc.OAuthError("invalid_request", "refresh_token required")
            result = svc.refresh_tokens(session, client_id, refresh_token)
        else:
            raise svc.OAuthError("unsupported_grant_type", grant_type)
    except svc.OAuthError as e:
        return _err(e)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


"""
Discovery documents (.well-known): when Claude hits /mcp and gets a 401, it follows these to learn where /register, /authorize and /token live. They are how Claude finds your login.
/register: Claude web registers itself automatically, so you never create a client ID by hand.
/authorize: this is the page you see in the browser when connecting an account. It is where an account becomes a user.
No redirects on bad input: sending an error to an unverified URL would be an open redirect.
/token: it trades the one-time code for tokens, and refreshes them later.
"""