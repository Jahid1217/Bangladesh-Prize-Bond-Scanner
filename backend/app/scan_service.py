"""Scan pipeline: frame dedupe, OCR decision, atomic persistence."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import settings
from .db import db, utc_now
from .ocr import OcrOutcome, OcrUnavailable, engine
from .serials import validate_serial

MAX_RAW_TEXT = 2000


class InvalidFrame(ValueError):
    pass


@dataclass
class BondRecord:
    id: int
    serial: str
    raw_text: str | None
    source: str
    confidence: float | None
    note: str | None
    created_at: str
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "serial": self.serial,
            "raw_text": self.raw_text,
            "source": self.source,
            "confidence": self.confidence,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FrameDeduplicator:
    """Rejects near-identical frames captured in quick succession."""

    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    def fingerprint(self, gray: np.ndarray) -> str:
        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        mean = float(small.mean())
        bits = 0
        for index, value in enumerate(small.flatten()):
            if value > mean:
                bits |= 1 << index
        return f"{bits:016x}"

    def is_duplicate(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            for old_key, stamp in list(self._seen.items()):
                if now - stamp > self.ttl * 4:
                    self._seen.pop(old_key, None)
            if key in self._seen and now - self._seen[key] <= self.ttl:
                self._seen[key] = now
                return True
            self._seen[key] = now
            return False


frame_dedupe = FrameDeduplicator(settings.frame_dedupe_seconds)


def decode_frame(data: bytes) -> np.ndarray:
    if not data:
        raise InvalidFrame("Empty upload")
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidFrame("Could not decode image; send a JPEG or PNG frame")
    height, width = image.shape[:2]
    if width < 120 or height < 40:
        raise InvalidFrame("Frame is too small; crop a wider serial area")
    if width * height > 25_000_000:
        raise InvalidFrame("Frame resolution is too large")
    return image


def _store_capture(data: bytes) -> str | None:
    """Persist frames that need manual review, relative to the captures dir."""
    try:
        settings.captures_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        folder = settings.captures_dir / day
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time() * 1000)}-{threading.get_ident() % 1000}.jpg"
        (folder / name).write_bytes(data)
        return f"{day}/{name}"
    except OSError:
        return None


def _serialize_attempt(row: Any) -> dict[str, Any]:
    keys = row.keys() if hasattr(row, "keys") else ()
    return {
        "id": row["id"],
        "serial": row["serial"],
        "status": row["status"],
        "confidence": row["confidence"],
        "raw_text": row["raw_text"],
        "reason": row["reason"],
        "image_path": row["image_path"],
        "processing_ms": row["processing_ms"],
        "created_at": row["created_at"],
        "bond_id": row["bond_id"] if "bond_id" in keys else None,
        "bond_serial": row["bond_serial"] if "bond_serial" in keys else None,
    }


def get_stats() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    with db.connection() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM bonds) AS total_unique,
              (SELECT COUNT(*) FROM scan_attempts) AS total_scans,
              (SELECT COUNT(*) FROM scan_attempts WHERE status = 'saved') AS saved_scans,
              (SELECT COUNT(*) FROM scan_attempts WHERE status = 'duplicate') AS duplicate_scans,
              (SELECT COUNT(*) FROM duplicate_attempts) AS duplicate_attempts,
              (SELECT COUNT(*) FROM scan_attempts WHERE status IN ('failed', 'uncertain')) AS failed_ocr,
              (SELECT COUNT(*) FROM scan_attempts WHERE status = 'uncertain') AS uncertain_scans,
              (SELECT COUNT(*) FROM bonds WHERE created_at >= ?) AS today_unique,
              (SELECT MAX(created_at) FROM scan_attempts) AS last_scan_at,
              (SELECT MAX(created_at) FROM bonds) AS last_saved_at
            """,
            (start_of_day,),
        ).fetchone()

    total_unique = int(row["total_unique"] or 0)
    target = settings.target_bonds
    remaining = max(0, target - total_unique)
    return {
        "total_unique": total_unique,
        "total_scanned": int(row["total_scans"] or 0),
        "saved_scans": int(row["saved_scans"] or 0),
        "duplicate_attempts": int(row["duplicate_attempts"] or 0),
        "duplicate_scans": int(row["duplicate_scans"] or 0),
        "failed_ocr_attempts": int(row["failed_ocr"] or 0),
        "uncertain_attempts": int(row["uncertain_scans"] or 0),
        "today_unique": int(row["today_unique"] or 0),
        "target": target,
        "remaining": remaining,
        "progress_percent": round(min(100.0, total_unique / target * 100.0), 1) if target else 0.0,
        "last_scan_at": row["last_scan_at"],
        "last_saved_at": row["last_saved_at"],
        "updated_at": utc_now(),
    }


def _persist_auto_scan(
    *,
    status: str,
    serial: str | None,
    confidence: float | None,
    raw_text: str,
    reason: str | None,
    image_path: str | None,
    processing_ms: int,
    variants: list[str],
    outcome_status: str,
) -> dict[str, Any]:
    """Atomically record the attempt, any new bond and any duplicate."""
    now = utc_now()
    with db.transaction(immediate=True) as conn:
        bond = None
        final_status = status
        if status == "saved" and serial:
            existing = conn.execute(
                "SELECT * FROM bonds WHERE serial = ?", (serial,)
            ).fetchone()
            if existing:
                final_status = "duplicate"
                conn.execute(
                    """INSERT INTO duplicate_attempts
                       (serial, bond_id, confidence, raw_text, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (serial, existing["id"], confidence, raw_text, now),
                )
                bond = existing
            else:
                cursor = conn.execute(
                    """INSERT INTO bonds
                       (serial, raw_text, source, confidence, note, created_at, updated_at)
                       VALUES (?, ?, 'auto', ?, NULL, ?, ?)""",
                    (serial, raw_text, confidence, now, now),
                )
                bond = conn.execute(
                    "SELECT * FROM bonds WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        elif status == "duplicate" and serial:
            existing = conn.execute(
                "SELECT * FROM bonds WHERE serial = ?", (serial,)
            ).fetchone()
            conn.execute(
                """INSERT INTO duplicate_attempts
                   (serial, bond_id, confidence, raw_text, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (serial, existing["id"] if existing else None, confidence, raw_text, now),
            )
            bond = existing

        cursor = conn.execute(
            """INSERT INTO scan_attempts
               (serial, bond_id, status, confidence, raw_text, reason, image_path,
                processing_ms, variants, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                serial,
                bond["id"] if bond else None,
                final_status,
                confidence,
                raw_text,
                reason,
                image_path,
                processing_ms,
                ",".join(variants),
                now,
            ),
        )
        attempt = conn.execute(
            "SELECT * FROM scan_attempts WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    stats = get_stats()
    return {
        "status": final_status,
        "ocr_status": outcome_status,
        "serial": serial,
        "confidence": confidence,
        "raw_text": raw_text,
        "reason": reason,
        "attempt": _serialize_attempt(attempt),
        "bond": BondRecord(**dict(bond)).as_dict() if bond else None,
        "stats": stats,
    }


def process_frame(image_bytes: bytes) -> dict[str, Any]:
    image = decode_frame(image_bytes)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fingerprint = frame_dedupe.fingerprint(gray)
    if frame_dedupe.is_duplicate(fingerprint):
        return {
            "status": "skipped",
            "ocr_status": "skipped",
            "serial": None,
            "confidence": None,
            "reason": "Identical frame already processed",
            "attempt": None,
            "bond": None,
            "stats": get_stats(),
        }

    try:
        outcome: OcrOutcome = engine.recognize(image)
    except OcrUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        now = utc_now()
        with db.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO scan_attempts
                   (serial, bond_id, status, confidence, raw_text, reason, image_path,
                    processing_ms, variants, created_at)
                   VALUES (NULL, NULL, 'failed', NULL, NULL, ?, NULL, 0, NULL, ?)""",
                (f"OCR error: {exc}"[:300], now),
            )
        return {
            "status": "failed",
            "ocr_status": "error",
            "serial": None,
            "confidence": None,
            "raw_text": "",
            "reason": f"OCR error: {exc}",
            "attempt": None,
            "bond": None,
            "stats": get_stats(),
        }

    if outcome.status == "no_serial":
        result = _persist_auto_scan(
            status="failed", serial=None, confidence=0.0,
            raw_text=outcome.raw_text[:MAX_RAW_TEXT], reason=outcome.reason,
            image_path=None, processing_ms=outcome.processing_ms,
            variants=outcome.variants, outcome_status=outcome.status,
        )
        return result

    if outcome.accepted and outcome.serial:
        return _persist_auto_scan(
            status="saved", serial=outcome.serial, confidence=outcome.confidence,
            raw_text=outcome.raw_text[:MAX_RAW_TEXT], reason=None,
            image_path=None, processing_ms=outcome.processing_ms,
            variants=outcome.variants, outcome_status=outcome.status,
        )

    # Uncertain reads are recorded and kept with an image for manual review.
    image_path = _store_capture(image_bytes)
    return _persist_auto_scan(
        status="uncertain", serial=outcome.serial, confidence=outcome.confidence,
        raw_text=outcome.raw_text[:MAX_RAW_TEXT],
        reason=outcome.reason or "Uncertain OCR result",
        image_path=image_path, processing_ms=outcome.processing_ms,
        variants=outcome.variants, outcome_status=outcome.status,
    )


def preview_ocr(image_bytes: bytes) -> dict[str, Any]:
    """Run OCR without writing anything (used by the tuning endpoint)."""
    image = decode_frame(image_bytes)
    outcome = engine.recognize(image)
    return {
        "status": outcome.status,
        "serial": outcome.serial,
        "confidence": outcome.confidence,
        "raw_text": outcome.raw_text,
        "variants": outcome.variants,
        "agreement": outcome.agreement,
        "reason": outcome.reason,
        "processing_ms": outcome.processing_ms,
    }


def save_bond(
    serial_input: str,
    *,
    note: str | None = None,
    attempt_id: int | None = None,
    confidence: float | None = None,
    raw_text: str | None = None,
) -> dict[str, Any]:
    validation = validate_serial(serial_input)
    if not validation.valid:
        return {"status": "invalid", "reason": validation.error, "serial": validation.serial}

    now = utc_now()
    status = "saved"
    bond = None
    with db.transaction(immediate=True) as conn:
        existing = conn.execute(
            "SELECT * FROM bonds WHERE serial = ?", (validation.serial,)
        ).fetchone()
        if existing:
            status = "duplicate"
            bond = existing
            conn.execute(
                """INSERT INTO duplicate_attempts
                   (serial, bond_id, confidence, raw_text, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (validation.serial, existing["id"], confidence, raw_text, now),
            )
            if attempt_id:
                conn.execute(
                    """UPDATE scan_attempts
                       SET status = 'duplicate', serial = ?, bond_id = ?, reason = ?
                       WHERE id = ?""",
                    (
                        validation.serial,
                        existing["id"],
                        "Manual entry matched an existing bond",
                        attempt_id,
                    ),
                )
        else:
            cursor = conn.execute(
                """INSERT INTO bonds
                   (serial, raw_text, source, confidence, note, created_at, updated_at)
                   VALUES (?, ?, 'manual', ?, ?, ?, ?)""",
                (validation.serial, raw_text, confidence, note, now, now),
            )
            bond = conn.execute(
                "SELECT * FROM bonds WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            if attempt_id:
                conn.execute(
                    """UPDATE scan_attempts
                       SET status = 'saved', serial = ?, bond_id = ?, reason = NULL
                       WHERE id = ?""",
                    (validation.serial, bond["id"], attempt_id),
                )

    return {
        "status": status,
        "serial": validation.serial,
        "bond": BondRecord(**dict(bond)).as_dict() if bond else None,
        "stats": get_stats(),
    }


def update_bond(
    bond_id: int, serial_input: str, note: str | None = None
) -> dict[str, Any] | None:
    validation = validate_serial(serial_input)
    if not validation.valid:
        return {"status": "invalid", "reason": validation.error}

    now = utc_now()
    with db.transaction(immediate=True) as conn:
        current = conn.execute("SELECT * FROM bonds WHERE id = ?", (bond_id,)).fetchone()
        if current is None:
            return None
        if validation.serial != current["serial"]:
            clash = conn.execute(
                "SELECT id FROM bonds WHERE serial = ? AND id != ?",
                (validation.serial, bond_id),
            ).fetchone()
            if clash:
                return {
                    "status": "duplicate",
                    "reason": f"Serial {validation.serial} already exists",
                    "existing_id": clash["id"],
                }
        new_note = note if note is not None else current["note"]
        conn.execute(
            "UPDATE bonds SET serial = ?, note = ?, updated_at = ? WHERE id = ?",
            (validation.serial, new_note, now, bond_id),
        )
        if validation.serial != current["serial"]:
            conn.execute(
                """INSERT INTO corrections
                   (bond_id, old_serial, new_serial, old_confidence, note, corrected_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    bond_id, current["serial"], validation.serial,
                    current["confidence"], note, now,
                ),
            )
        bond = conn.execute("SELECT * FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    return {"status": "updated", "bond": BondRecord(**dict(bond)).as_dict()}


def get_bond_corrections(bond_id: int) -> list[dict[str, Any]]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM corrections WHERE bond_id = ? ORDER BY corrected_at DESC",
            (bond_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_bonds(search: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    clause = ""
    params: list[Any] = []
    if search:
        clause = "WHERE serial LIKE ? OR raw_text LIKE ?"
        params = [f"%{search}%", f"%{search}%"]
    with db.connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM bonds {clause}", params
        ).fetchone()["n"]
        rows = conn.execute(
            f"SELECT * FROM bonds {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "items": [BondRecord(**dict(row)).as_dict() for row in rows],
    }


def list_attempts(limit: int = 25, status: str | None = None) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    filters = ""
    params: list[Any] = []
    if status:
        filters = "AND a.status = ?"
        params.append(status)
    with db.connection() as conn:
        rows = conn.execute(
            f"""SELECT a.*, b.serial AS bond_serial
                FROM scan_attempts a
                LEFT JOIN bonds b ON b.id = a.bond_id
                WHERE 1 = 1 {filters}
                ORDER BY a.id DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
    return {"items": [_serialize_attempt(row) for row in rows]}


def capture_path(relative: str) -> Path | None:
    root = settings.captures_dir.resolve()
    target = (root / relative).resolve()
    if root not in target.parents or not target.is_file():
        return None
    return target
