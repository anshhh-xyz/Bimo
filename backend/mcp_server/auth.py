import hmac
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


def bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def resolve_token(token: str | None) -> int | None:
    """Static dev token first (Inspector, curl), then a real OAuth access token."""
    if not token:
        return None
    for known, user_id in dev_tokens().items():
        if hmac.compare_digest(known, token):   # constant-time compare
            return user_id
    with SessionLocal() as session:
        return oauth.user_for_access_token(session, token)


def caller_from_headers(headers) -> Caller:
    user_id = resolve_token(bearer_token(headers.get("authorization")))
    if user_id is None:
        raise Unauthorized("Missing or invalid bearer token")
    surface = (headers.get("x-surface") or "web").lower()
    if surface not in MCP_SURFACES:
        raise InvalidInput("X-Surface must be 'web' or 'code'")
    return Caller(user_id, surface)


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