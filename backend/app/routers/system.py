from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..db import db
from ..ocr import engine
from ..scan_service import get_stats

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    info = engine.info()
    database = db.health()
    ocr_ok = info.available
    return {
        "status": "ok" if database["ok"] and ocr_ok else "degraded",
        "app": "prize-bond-scanner",
        "version": "1.0.0",
        "database": database,
        "ocr": {
            "available": info.available,
            "version": info.version,
            "command": info.command,
            "requested_languages": info.requested_languages,
            "active_languages": info.active_languages,
            "available_languages": info.available_languages,
            "error": info.error,
        },
        "config": {
            "target": settings.target_bonds,
            "auto_save_confidence": settings.auto_save_confidence,
            "min_confidence": settings.min_confidence,
            "serial_pattern": settings.serial_pattern,
            "timezone": settings.timezone,
            "frame_dedupe_seconds": settings.frame_dedupe_seconds,
        },
    }


@router.get("/stats")
def stats():
    return get_stats()
