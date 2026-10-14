from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from mcp_server.server import mcp, mcp_asgi_app
from app.routers import projects, tasks, decisions, changes, handoffs
from app.services.errors import ConflictError, ServiceError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # A mounted sub-app's own lifespan never runs, so we start MCP's session manager here.
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Memory & Handoff", lifespan=lifespan)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    body = {"detail": exc.message}
    if isinstance(exc, ConflictError):
        body = {"detail": "Version conflict", "current": exc.current}
    return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(body))


@app.get("/health")
def health():
    return {"ok": True}


for r in (projects, tasks, decisions, changes, handoffs):
    app.include_router(r.router)

# Mount LAST. Starlette matches in order, so every FastAPI route above wins and
# only unmatched paths reach MCP, which gives the endpoint exactly /mcp
# (mounting at "/mcp" would force "/mcp/" and a 307 redirect that some clients mishandle).
app.mount("/", mcp_asgi_app)