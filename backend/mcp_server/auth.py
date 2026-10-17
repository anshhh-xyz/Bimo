import hmac
import re
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from app.config import dev_tokens, public_url
from app.db import SessionLocal
from app.services import oauth
from app.services.errors import InvalidInput, Unauthorized

MCP_SURFACES = {"web", "code"}


@dataclass(frozen=True)
class Caller:
    user_id: int
    surface: str
    agent: str | None = None


def bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def classify_client(client_name: str | None) -> tuple[str | None, str | None]:
    """Map the OAuth client name to (agent, surface). Unknown clients keep a
    slug of their own name as agent and no surface opinion."""
    n = (client_name or "").strip().lower()
    if not n:
        return None, None
    if "claude" in n and "code" in n:
        return "claude-code", "code"
    if "claude" in n:
        return "claude", "web"
    if "chatgpt" in n or "openai" in n:
        return "chatgpt", "web"
    return (re.sub(r"[^a-z0-9._-]+", "-", n).strip("-")[:50] or None), None


def resolve_identity(token: str | None) -> tuple[int, str | None] | None:
    """(user_id, client_name). Static dev token first, then OAuth access token.
    Dev tokens have no client, so their writes carry no agent label."""
    if not token:
        return None
    for known, user_id in dev_tokens().items():
        if hmac.compare_digest(known, token):   # constant-time compare
            return user_id, None
    with SessionLocal() as session:
        return oauth.identity_for_access_token(session, token)


def resolve_token(token: str | None) -> int | None:
    ident = resolve_identity(token)
    return ident[0] if ident else None


def caller_from_headers(headers) -> Caller:
    ident = resolve_identity(bearer_token(headers.get("authorization")))
    if ident is None:
        raise Unauthorized("Missing or invalid bearer token")
    user_id, client_name = ident
    agent, client_surface = classify_client(client_name)
    # An explicit X-Surface header wins; otherwise infer from the client; else web.
    surface = (headers.get("x-surface") or client_surface or "web").lower()
    if surface not in MCP_SURFACES:
        raise InvalidInput("X-Surface must be 'web' or 'code'")
    return Caller(user_id, surface, agent)


def _challenge_header() -> str:
    base = public_url()
    if not base:
        return "Bearer"
    return f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource"'


class BearerAuthMiddleware:
    """Pure ASGI. Rejects /mcp requests without a valid token and points the
    client at the OAuth discovery document, which is what starts the login flow."""

    def __init__(self, app, prefix: str = "/mcp"):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (
                scope["path"] == self.prefix or scope["path"].startswith(self.prefix + "/")):
            token = bearer_token(Headers(scope=scope).get("authorization"))
            # DB lookup is synchronous, so keep it off the event loop
            if await run_in_threadpool(resolve_token, token) is None:
                response = JSONResponse({"error": "unauthorized"}, status_code=401,
                                        headers={"WWW-Authenticate": _challenge_header()})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)