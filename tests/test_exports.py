from __future__ import annotations

import io
import time

from openpyxl import load_workbook

from app.db import db, utc_now
from app.exports import build_xlsx, build_csv
from app.serials import to_bengali_digits
from tests.test_api import unique_serial


def test_xlsx_export_preserves_leading_zeros_and_bengali(client):
    serial = "0" + unique_serial()[1:]
    note = "সংরক্ষিত কপি"
    client.post("/api/bonds", json={"serial": serial, "note": note})

    response = client.get("/api/exports/xlsx")
    assert response.status_code == 200
    assert "spreadsheetml.sheet" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]

    workbook = load_workbook(io.BytesIO(response.content))
    sheet = workbook["Prize Bonds"]
    headers = [cell.value for cell in sheet[1]]
    assert headers[:3] == ["Serial Number", "সিরিয়াল (বাংলা)", "Scanned At"]

    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    match = next(row for row in rows if row[0] == serial)
    assert isinstance(match[0], str)
    assert match[1] == to_bengali_digits(serial)
    assert match[5] == note
    assert workbook["Summary"]["A1"].value == "Bangladesh Prize Bond Scanner"


def test_csv_export_has_bom_and_bengali(client):
    response = client.get("/api/exports/csv")
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    assert "Serial Number" in text
    assert "সিরিয়াল (বাংলা)" in text
    assert "text/csv" in response.headers["content-type"]


def test_export_handles_2000_records_quickly(client):
    now = utc_now()
    rows = [
        (f"80{i:05d}", "perf-test", now, now)
        for i in range(2000)
    ]
    with db.transaction(immediate=True) as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO bonds
               (serial, raw_text, source, confidence, note, created_at, updated_at)
               VALUES (?, NULL, 'manual', NULL, ?, ?, ?)""",
            [(serial, note, created, updated) for serial, note, created, updated in rows],
        )
    try:
        started = time.perf_counter()
        stats = client.get("/api/stats").json()
        xlsx = build_xlsx()
        elapsed = time.perf_counter() - started
        assert stats["total_unique"] >= 2000
        assert xlsx.row_count >= 2000
        assert elapsed < 15, f"2000-row stats+export took {elapsed:.1f}s"
        assert len(xlsx.data) > 10_000
        csv = build_csv()
        assert csv.row_count == xlsx.row_count
    finally:
        with db.transaction(immediate=True) as conn:
            conn.execute("DELETE FROM bonds WHERE note = 'perf-test'")
