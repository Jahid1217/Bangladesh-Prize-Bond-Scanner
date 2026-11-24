"""XLSX / CSV exports with Bengali-safe encoding."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import settings
from .db import db
from .serials import to_bengali_digits

HEADERS = [
    "Serial Number",
    "সিরিয়াল (বাংলা)",
    "Scanned At",
    "Source",
    "Confidence (%)",
    "Note",
]


@dataclass
class ExportFile:
    filename: str
    data: bytes
    content_type: str
    row_count: int
    path: Path | None = None


def _local_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return value or ""


def _rows() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT id, serial, source, confidence, note, created_at
               FROM bonds ORDER BY created_at ASC, id ASC"""
        ).fetchall()
    return [dict(row) for row in rows]


def _summary_counts() -> dict[str, int]:
    with db.connection() as conn:
        row = conn.execute(
            """SELECT
                 (SELECT COUNT(*) FROM bonds) AS unique_bonds,
                 (SELECT COUNT(*) FROM duplicate_attempts) AS duplicates,
                 (SELECT COUNT(*) FROM scan_attempts WHERE status IN ('failed','uncertain')) AS failed
            """
        ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def _stamp() -> str:
    return datetime.now(ZoneInfo(settings.timezone)).strftime("%Y%m%d_%H%M%S")


def _prune(directory: Path) -> None:
    files = sorted(directory.glob("prize_bonds_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[settings.max_exports_kept:]:
        try:
            old.unlink()
        except OSError:
            pass


def _save_copy(filename: str, data: bytes) -> Path | None:
    try:
        settings.exports_dir.mkdir(parents=True, exist_ok=True)
        target = settings.exports_dir / filename
        target.write_bytes(data)
        _prune(settings.exports_dir)
        return target
    except OSError:
        return None


def build_xlsx() -> ExportFile:
    rows = _rows()
    counts = _summary_counts()
    wb = Workbook()
    ws = wb.active
    ws.title = "Prize Bonds"

    header_fill = PatternFill("solid", fgColor="115E59")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for column, title in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=column, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for index, row in enumerate(rows, start=2):
        serial_cell = ws.cell(row=index, column=1, value=row["serial"])
        serial_cell.number_format = "@"
        bangla_cell = ws.cell(row=index, column=2, value=to_bengali_digits(row["serial"]))
        bangla_cell.number_format = "@"
        ws.cell(row=index, column=3, value=_local_timestamp(row["created_at"]))
        ws.cell(row=index, column=4, value=row["source"])
        ws.cell(row=index, column=5, value=round(row["confidence"], 1) if row["confidence"] is not None else "")
        note_cell = ws.cell(row=index, column=6, value=row["note"] or "")
        for column in range(1, len(HEADERS) + 1):
            ws.cell(row=index, column=column).border = border

    widths = [20, 20, 21, 10, 15, 40]
    for column, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{max(1, len(rows) + 1)}"

    summary = wb.create_sheet("Summary")
    summary.column_dimensions["A"].width = 30
    summary.column_dimensions["B"].width = 34
    entries = [
        ("Export generated", datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("Target", settings.target_bonds),
        ("Total unique bonds", counts["unique_bonds"]),
        ("Remaining target", max(0, settings.target_bonds - counts["unique_bonds"])),
        ("Duplicate scan attempts", counts["duplicates"]),
        ("Failed / uncertain OCR attempts", counts["failed"]),
        ("Database", str(settings.database_path)),
    ]
    summary["A1"] = "Bangladesh Prize Bond Scanner"
    summary["A1"].font = Font(bold=True, size=14, color="115E59")
    for index, (label, value) in enumerate(entries, start=3):
        summary.cell(row=index, column=1, value=label).font = Font(bold=True)
        summary.cell(row=index, column=2, value=value)

    stream = io.BytesIO()
    wb.save(stream)
    data = stream.getvalue()
    filename = f"prize_bonds_{_stamp()}.xlsx"
    path = _save_copy(filename, data)
    return ExportFile(
        filename=filename,
        data=data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        row_count=len(rows),
        path=path,
    )


def build_csv() -> ExportFile:
    rows = _rows()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADERS)
    for row in rows:
        writer.writerow([
            row["serial"],
            to_bengali_digits(row["serial"]),
            _local_timestamp(row["created_at"]),
            row["source"],
            round(row["confidence"], 1) if row["confidence"] is not None else "",
            row["note"] or "",
        ])
    # BOM keeps Bengali text readable when opened directly in Excel.
    data = "\ufeff".encode("utf-8") + buffer.getvalue().encode("utf-8")
    filename = f"prize_bonds_{_stamp()}.csv"
    path = _save_copy(filename, data)
    return ExportFile(
        filename=filename,
        data=data,
        content_type="text/csv; charset=utf-8",
        row_count=len(rows),
        path=path,
    )
