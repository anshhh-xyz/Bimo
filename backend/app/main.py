from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.errors import ConflictError
from app.routers import projects, tasks, decisions, changes, handoffs

app = FastAPI(title="Memory & Handoff")

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409,
                        content=jsonable_encoder({"detail": "Version conflict",
                                                  "current": exc.current}))

@app.get("/health")
def health():
    return {"ok": True}

for r in (projects, tasks, decisions, changes, handoffs):
    app.include_router(r.router)