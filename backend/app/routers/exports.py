from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from ..exports import build_csv, build_xlsx

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _download(data: bytes, filename: str, media_type: str) -> Response:
    disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition, "Cache-Control": "no-store"},
    )


@router.get("/xlsx")
async def export_xlsx():
    result = await run_in_threadpool(build_xlsx)
    return _download(result.data, result.filename, result.content_type)


@router.get("/csv")
async def export_csv():
    result = await run_in_threadpool(build_csv)
    return _download(result.data, result.filename, result.content_type)
