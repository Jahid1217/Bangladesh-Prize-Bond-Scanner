from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import db
from .ocr import engine
from .routers import bonds, exports, scans, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    settings.captures_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    engine.info()
    yield


app = FastAPI(
    title="Bangladesh Prize Bond Scanner",
    version="1.0.0",
    description="Local OCR scanning, duplicate-safe storage and Excel export for prize bonds.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(scans.router)
app.include_router(bonds.router)
app.include_router(exports.router)


def _index_file() -> Path | None:
    index = settings.frontend_dist / "index.html"
    return index if index.is_file() else None


if settings.serve_frontend and (settings.frontend_dist / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=settings.frontend_dist / "assets"),
        name="assets",
    )


@app.get("/", include_in_schema=False)
def root():
    index = _index_file()
    if index:
        return FileResponse(index)
    return JSONResponse(
        {
            "app": "prize-bond-scanner",
            "message": "API is running. Build the frontend (npm run build) "
                       "or use the Vite dev server.",
            "docs": "/docs",
            "health": "/api/health",
        }
    )


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Not found")
    if settings.serve_frontend and _index_file():
        candidate = (settings.frontend_dist / full_path).resolve()
        dist_root = settings.frontend_dist.resolve()
        if dist_root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_index_file())
    raise HTTPException(status_code=404, detail="Frontend build not found")
