from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..db import db
from ..ocr import OcrUnavailable
from ..scan_service import (
    InvalidFrame,
    capture_path,
    list_attempts,
    preview_ocr,
    process_frame,
)

router = APIRouter(prefix="/api", tags=["scans"])

MAX_BYTES = settings.max_upload_mb * 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Frame exceeds {settings.max_upload_mb} MB limit",
        )
    return data


@router.post("/scans/frame")
async def scan_frame(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        return await run_in_threadpool(process_frame, data)
    except InvalidFrame as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OcrUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"OCR engine unavailable: {exc}",
        ) from exc


@router.post("/ocr/preview")
async def ocr_preview(file: UploadFile = File(...)):
    """Run OCR and return the raw result without saving anything."""
    data = await _read_upload(file)
    try:
        return await run_in_threadpool(preview_ocr, data)
    except InvalidFrame as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OcrUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"OCR engine unavailable: {exc}") from exc


@router.get("/scans")
def recent_scans(
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
):
    if status and status not in {"saved", "duplicate", "uncertain", "failed"}:
        raise HTTPException(status_code=400, detail="Unknown scan status")
    return list_attempts(limit=limit, status=status)


@router.get("/scans/{attempt_id}/image")
def scan_image(attempt_id: int):
    with db.connection() as conn:
        row = conn.execute(
            "SELECT image_path FROM scan_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    if not row or not row["image_path"]:
        raise HTTPException(status_code=404, detail="No capture stored for this scan")
    path = capture_path(row["image_path"])
    if path is None:
        raise HTTPException(status_code=404, detail="Capture file is missing")
    return FileResponse(path, media_type="image/jpeg")
