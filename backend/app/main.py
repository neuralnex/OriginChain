from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import get_settings
from .db import Base, engine
from . import models  # noqa: F401 - register SQLAlchemy tables


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="OriginChain API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(router)


@app.middleware("http")
async def enforce_request_size(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "invalid Content-Length"})
        max_size = ((get_settings().max_upload_bytes + 2) // 3) * 4 + 2_000_000
        if size > max_size:
            return JSONResponse(status_code=413, content={"detail": "request exceeds configured upload limit"})
    return await call_next(request)


@app.get("/", include_in_schema=False)
def root():
    return {"service": "OriginChain API", "docs": "/docs", "api": "/v1"}
