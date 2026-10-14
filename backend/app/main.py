from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.routers import projects, tasks, decisions, changes, handoffs
from app.services.errors import ConflictError, ServiceError

app = FastAPI(title="Memory & Handoff")


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