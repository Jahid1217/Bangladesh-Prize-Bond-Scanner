from __future__ import annotations

import itertools
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.config import settings
from app.db import db, utc_now
from app.scan_service import save_bond
from tests.support import frame_bytes

_counter = itertools.count(100)


def unique_serial() -> str:
    return f"7{next(_counter):06d}"[:7]


def scan(client, serial: str, *, bengali: bool = False, quality: int = 92,
         rotation: float = 0.0):
    return client.post(
        "/api/scans/frame",
        files={
            "file": (
                "frame.jpg",
                frame_bytes(serial, bengali=bengali, quality=quality, rotation=rotation),
                "image/jpeg",
            )
        },
    )


def test_health_reports_ocr_and_database(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["ok"] is True
    assert body["config"]["target"] == 2000
    assert "available" in body["ocr"]


@pytest.mark.skipif(not settings.tesseract_cmd, reason="Tesseract not available")
def test_scan_save_duplicate_and_dedupe(client):
    serial = unique_serial()
    before = client.get("/api/stats").json()

    first = scan(client, serial)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "saved", body
    assert body["serial"] == serial
    assert body["bond"]["serial"] == serial
    assert body["stats"]["total_unique"] == before["total_unique"] + 1

    # Identical frame is ignored before OCR runs.
    skipped = scan(client, serial)
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"

    # A visually different frame with the same serial is a duplicate attempt.
    duplicate = scan(client, serial, rotation=1.6)
    assert duplicate.status_code == 200, duplicate.text
    dup_body = duplicate.json()
    assert dup_body["status"] == "duplicate"
    assert dup_body["serial"] == serial
    assert dup_body["stats"]["duplicate_attempts"] >= 1
    assert dup_body["stats"]["total_unique"] == before["total_unique"] + 1

    # Manual duplicate request is rejected by the API.
    conflict = client.post("/api/bonds", json={"serial": serial})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["serial"] == serial


def test_manual_entry_validation_and_correction_history(client):
    serial = unique_serial()
    created = client.post(
        "/api/bonds", json={"serial": serial, "note": "manual entry"}
    )
    assert created.status_code == 200, created.text
    bond = created.json()["bond"]
    assert bond["source"] == "manual"

    invalid = client.post("/api/bonds", json={"serial": "12"})
    assert invalid.status_code == 422

    new_serial = unique_serial()
    updated = client.patch(f"/api/bonds/{bond['id']}", json={"serial": new_serial})
    assert updated.status_code == 200, updated.text
    assert updated.json()["bond"]["serial"] == new_serial

    history = client.get(f"/api/bonds/{bond['id']}/corrections")
    assert history.status_code == 200
    items = history.json()["items"]
    assert items and items[0]["old_serial"] == serial
    assert items[0]["new_serial"] == new_serial

    other = client.post("/api/bonds", json={"serial": unique_serial()}).json()["bond"]
    clash = client.patch(f"/api/bonds/{other['id']}", json={"serial": new_serial})
    assert clash.status_code == 409


def test_history_row_links_to_current_serial_after_correction(client):
    serial = unique_serial()
    bond = client.post("/api/bonds", json={"serial": serial}).json()["bond"]
    now = utc_now()
    with db.transaction(immediate=True) as conn:
        cursor = conn.execute(
            """INSERT INTO scan_attempts
               (serial, bond_id, status, confidence, raw_text, reason, image_path,
                processing_ms, variants, created_at)
               VALUES (?, ?, 'saved', 90, NULL, NULL, NULL, 100, 'otsu', ?)""",
            (serial, bond["id"], now),
        )
        attempt_id = cursor.lastrowid

    new_serial = unique_serial()
    assert client.patch(f"/api/bonds/{bond['id']}", json={"serial": new_serial}).status_code == 200

    items = client.get("/api/scans", params={"limit": 50}).json()["items"]
    attempt = next(item for item in items if item["id"] == attempt_id)
    assert attempt["serial"] == serial
    assert attempt["bond_id"] == bond["id"]
    assert attempt["bond_serial"] == new_serial


def test_bond_listing_search_and_pagination(client):
    serial = unique_serial()
    client.post("/api/bonds", json={"serial": serial})
    listing = client.get("/api/bonds", params={"search": serial, "limit": 10})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert any(item["serial"] == serial for item in body["items"])


@pytest.mark.skipif(not settings.tesseract_cmd, reason="Tesseract not available")
def test_bengali_scan_can_be_confirmed_manually(client):
    serial = "1435003"
    result = scan(client, serial, bengali=True)
    assert result.status_code == 200, result.text
    body = result.json()
    if body["status"] == "uncertain":
        confirmed = client.post(
            "/api/bonds",
            json={"serial": serial, "attempt_id": body["attempt"]["id"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["status"] in {"saved", "duplicate"}
    else:
        # If the engine was confident it must have read the serial correctly.
        assert body["serial"] == serial
        assert body["status"] in {"saved", "duplicate"}


def test_concurrent_duplicate_insertions_are_impossible(client):
    serial = unique_serial()

    def attempt(_: int):
        return save_bond(serial, note="race test")["status"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert results.count("saved") == 1
    assert results.count("duplicate") == 7
    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM bonds WHERE serial = ?", (serial,)
        ).fetchone()["n"]
    assert count == 1


def test_scan_history_and_stats_shape(client):
    stats = client.get("/api/stats").json()
    for key in (
        "total_unique", "total_scanned", "duplicate_attempts", "failed_ocr_attempts",
        "uncertain_attempts", "remaining", "target", "progress_percent",
    ):
        assert key in stats
    history = client.get("/api/scans", params={"limit": 5})
    assert history.status_code == 200
    assert isinstance(history.json()["items"], list)


def test_data_survives_a_new_connection(client):
    serial = unique_serial()
    client.post("/api/bonds", json={"serial": serial})
    conn = sqlite3.connect(settings.database_path)
    try:
        row = conn.execute(
            "SELECT serial FROM bonds WHERE serial = ?", (serial,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
