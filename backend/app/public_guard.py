import os
from starlette.responses import PlainTextResponse

# Everything the internet is allowed to reach when PUBLIC_MODE=1.
ALLOWED = ("/mcp", "/.well-known", "/authorize", "/token", "/register", "/health")


class PublicGuard:
    """Pure ASGI. In PUBLIC_MODE the REST routes return 404, because they still
    trust the X-User-Id header and must never be reachable through the tunnel."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and os.environ.get("PUBLIC_MODE") == "1":
            path = scope["path"]
            if not any(path == p or path.startswith(p + "/") for p in ALLOWED):
                await PlainTextResponse("Not found", status_code=404)(scope, receive, send)
                return
        await self.app(scope, receive, send)

"""Without it, anyone who finds your tunnel URL could call /projects/1/tasks with X-User-Id: 1. Real REST auth comes later, and until then this guard is the lock."""
