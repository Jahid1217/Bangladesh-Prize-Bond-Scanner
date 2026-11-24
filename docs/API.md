# API reference

Base URL: `http://localhost:8000` or `https://<laptop-ip>:8443`.
Interactive OpenAPI docs: `/docs`.

All responses are JSON unless they are file downloads. Errors use FastAPI's
`{"detail": ...}` shape. No authentication — keep the server on a trusted LAN.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend, database and OCR status |
| GET | `/api/stats` | Dashboard counters |
| POST | `/api/scans/frame` | Run OCR on a frame and persist the attempt |
| POST | `/api/ocr/preview` | Run OCR without writing anything |
| GET | `/api/scans?limit=25&status=` | Recent scan attempts |
| GET | `/api/scans/{id}/image` | Captured frame for an attempt (if stored) |
| GET | `/api/bonds?search=&limit=&offset=` | Saved bonds, newest first |
| POST | `/api/bonds` | Manual add or confirm a reviewed serial |
| PATCH | `/api/bonds/{id}` | Correct a serial / note |
| GET | `/api/bonds/{id}/corrections` | Correction history |
| GET | `/api/exports/xlsx` | Download Excel |
| GET | `/api/exports/csv` | Download CSV |

## Health

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "ok",
  "database": { "ok": true, "bonds": 2, "path": ".../database/prize_bonds.db" },
  "ocr": {
    "available": true,
    "version": "5.5.0",
    "active_languages": "ben+eng",
    "requested_languages": "ben+eng",
    "error": null
  },
  "config": { "target": 2000, "auto_save_confidence": 72.0, "timezone": "Asia/Dhaka" }
}
```

`status` is `degraded` when the database check fails or OCR is unavailable. The
dashboard still allows manual entry and exports in that state.

## Scan a frame

```bash
curl -X POST http://localhost:8000/api/scans/frame \
  -F "file=@frame.jpg;type=image/jpeg"
```

Response (`status` is one of `saved`, `duplicate`, `uncertain`, `failed`,
`skipped`):

```json
{
  "status": "saved",
  "ocr_status": "ok",
  "serial": "7771234",
  "confidence": 96.0,
  "raw_text": "7771234",
  "reason": null,
  "attempt": { "id": 3, "serial": "7771234", "status": "saved", "...": "..." },
  "bond": { "id": 2, "serial": "7771234", "source": "auto", "...": "..." },
  "stats": { "total_unique": 2, "total_scanned": 3, "remaining": 1998 }
}
```

- `skipped`: identical frame already processed recently; nothing was recorded.
- `duplicate`: valid OCR but the serial exists; tracked in `duplicate_attempts`.
- `uncertain`: candidate exists but confidence/consensus is insufficient. The
  serial is a suggestion, not a bond. Confirm through `POST /api/bonds` with
  `attempt_id`.
- `failed`: no valid serial. `reason` explains it.
- HTTP 400: undecodable or too-small image.
- HTTP 413: over `PBS_MAX_UPLOAD_MB` (default 12 MB).
- HTTP 503: Tesseract unavailable.

Frame fingerprints are cached for `PBS_FRAME_DEDUPE_SECONDS`, so sending the same
image twice quickly returns `skipped` rather than creating attempts.

## Preview OCR (no writes)

```bash
curl -X POST http://localhost:8000/api/ocr/preview -F "file=@frame.jpg"
```

Returns serial, confidence, variants, agreement, raw text and `processing_ms`.
Useful for tuning without polluting stats.

## Bonds

```bash
# list / search
curl "http://localhost:8000/api/bonds?search=777&limit=20"

# manual entry (also used to confirm a review)
curl -X POST http://localhost:8000/api/bonds \
  -H 'Content-Type: application/json' \
  -d '{"serial":"০৭৮৬৩৪৫","note":"bundle A","attempt_id":12}'

# correct a serial
curl -X PATCH http://localhost:8000/api/bonds/2 \
  -H 'Content-Type: application/json' \
  -d '{"serial":"7771235"}'

# correction history
curl http://localhost:8000/api/bonds/2/corrections
```

- `serial` accepts Bengali or ASCII digits; response and storage use ASCII.
- `attempt_id` (optional) marks a reviewed scan as saved/duplicate.
- Validation failure → 422 with the reason.
- Duplicate serial → 409 with `{message, serial, bond, stats}`.
- PATCH keeps the previous value in `corrections`.

## Scan history

```bash
curl "http://localhost:8000/api/scans?limit=10&status=duplicate"
```

Returns `{items: [...]}` with `serial`, `status`, `confidence`, `reason`,
`image_path`, `processing_ms`, `created_at` and `bond_id` (when a bond exists for
that serial).

## Stats

```bash
curl http://localhost:8000/api/stats
```

| Field | Meaning |
| --- | --- |
| `total_unique` | Rows in `bonds` |
| `total_scanned` | All processed scan attempts (saved + duplicate + uncertain + failed) |
| `saved_scans` | Attempts that created a bond |
| `duplicate_attempts` | Entries in `duplicate_attempts` |
| `duplicate_scans` | Attempts with duplicate status |
| `failed_ocr_attempts` | failed + uncertain attempts |
| `uncertain_attempts` | Attempts waiting for/handled by review |
| `today_unique` | Bonds added since midnight UTC |
| `target`, `remaining`, `progress_percent` | Derived from `PBS_TARGET` |
| `last_scan_at`, `last_saved_at` | ISO UTC timestamps |

## Exports

```bash
curl -OJ http://localhost:8000/api/exports/xlsx
curl -OJ http://localhost:8000/api/exports/csv
```

Filenames: `prize_bonds_YYYYmmdd_HHMMSS.xlsx|.csv`, timestamps in
`PBS_TIMEZONE` (Asia/Dhaka by default). Each response also writes a copy to the
exports directory (latest 20 kept).

XLSX sheets:

- **Prize Bonds** — serial (text), Bangla-digit serial, scan time, source,
  confidence, note; frozen header + autofilter.
- **Summary** — export time, target, unique count, remaining, duplicate attempts,
  failed/uncertain OCR, database path.

CSV is UTF-8 with BOM, RFC 4180 quoting, same columns.

## Error codes

| Code | Meaning |
| --- | --- |
| 400 | Bad image / unknown scan status |
| 404 | Bond, attempt or capture not found |
| 409 | Duplicate serial |
| 413 | Upload too large |
| 422 | Invalid serial/body |
| 503 | OCR engine unavailable |
