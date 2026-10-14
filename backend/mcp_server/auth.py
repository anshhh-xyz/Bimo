import hmac
from dataclasses import dataclass
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from app.config import dev_tokens
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
    if not token:
        return None
    for known, user_id in dev_tokens().items():
        if hmac.compare_digest(known, token):   # constant-time compare
            return user_id
    return None


def caller_from_headers(headers) -> Caller:
    user_id = resolve_token(bearer_token(headers.get("authorization")))
    if user_id is None:
        raise Unauthorized("Missing or invalid bearer token")
    surface = (headers.get("x-surface") or "web").lower()
    if surface not in MCP_SURFACES:
        raise InvalidInput("X-Surface must be 'web' or 'code'")
    return Caller(user_id, surface)


class BearerAuthMiddleware:
    """Pure ASGI (not BaseHTTPMiddleware, which breaks streaming responses).
    Rejects /mcp requests without a valid token before MCP sees them."""

    def __init__(self, app, prefix: str = "/mcp"):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (
                scope["path"] == self.prefix or scope["path"].startswith(self.prefix + "/")):
            token = bearer_token(Headers(scope=scope).get("authorization"))
            if resolve_token(token) is None:
                response = JSONResponse({"error": "unauthorized"}, status_code=401,
                                        headers={"WWW-Authenticate": "Bearer"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

"""The middleware returns a proper HTTP 401 at the door, 
which clients expect and which OAuth discovery will need later. The tools re-resolve the identity per call. 
surface comes from an X-Surface header, so a Claude Code connection can declare itself code and its writes get labeled correctly for provenance. 
github is deliberately not allowed here, because that surface is reserved for the webhook in Phase 5."""