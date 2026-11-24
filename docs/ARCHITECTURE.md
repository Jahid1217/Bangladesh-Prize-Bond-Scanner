# Architecture

## Components

```
┌───────────────────────────── phone (Vivo V21) ────────────────────────────┐
│ React dashboard served by FastAPI over HTTPS                              │
│  • getUserMedia rear camera (1920×1080)                                   │
│  • guide-frame crop, brightness/sharpness/contrast gate                    │
│  • 8×8 average-hash dedupe, 750 ms loop, cooldown                          │
│  • review card for uncertain reads, manual entry, history, edit            │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ multipart JPEG over Wi-Fi
┌───────────────────────────────▼───────────────────────────────────────────┐
│ FastAPI (uvicorn)                                                          │
│  routers: scans / bonds / exports / system                                │
│  threadpool for OCR + SQLite (event loop stays responsive)                 │
│  single OCR lock → one CPU-heavy Tesseract run at a time                   │
└───────┬───────────────────────────┬───────────────────────┬───────────────┘
        │                           │                       │
┌───────▼─────────┐      ┌──────────▼──────────┐   ┌────────▼──────────────┐
│ OCR pipeline    │      │ SQLite (WAL)         │   │ Export builder        │
│ OpenCV variants │      │ bonds UNIQUE(serial) │   │ openpyxl / csv        │
│ Tesseract 5     │      │ scan_attempts        │   │ Bengali-safe XLSX/CSV │
│ consensus       │      │ duplicate_attempts   │   │ exports/ copies       │
└─────────────────┘      │ corrections          │   └───────────────────────┘
                         └──────────────────────┘
```

The frontend is a static build served by the backend. There is no separate
frontend server in production; `frontend/dist` is mounted by `app/main.py`, with
an SPA fallback for non-`/api` routes.

## Database schema

```sql
bonds(
  id INTEGER PRIMARY KEY,
  serial TEXT NOT NULL UNIQUE,       -- canonical ASCII, leading zeros kept
  raw_text TEXT,                     -- OCR text that produced it
  source TEXT CHECK (auto|manual),
  confidence REAL,
  note TEXT,
  created_at TEXT, updated_at TEXT   -- ISO-8601 UTC
)

scan_attempts(
  id, serial, bond_id → bonds (SET NULL),
  status CHECK(saved|duplicate|uncertain|failed),
  confidence, raw_text, reason, image_path,
  processing_ms, variants, created_at
)

duplicate_attempts(id, serial, bond_id → bonds, confidence, raw_text, created_at)

corrections(id, bond_id → bonds, old_serial, new_serial,
            old_confidence, note, corrected_at)
```

Indexes cover `created_at DESC` and `scan_attempts.status`. Foreign keys are
enabled; deleting a bond cascades corrections and nulls duplicate references.

The `UNIQUE` constraint on `bonds.serial` is the last line of defence and is not
optional. All writes go through one `BEGIN IMMEDIATE` transaction that checks for
an existing serial, inserts the bond, records the duplicate or attempt and commits
atomically.

`scan_attempts.bond_id` is written at scan time so a history row stays linked to
the right bond even after the serial is corrected. Databases created by version 1
are migrated automatically on startup (column added, existing rows backfilled by
serial where possible).

## Scan flow (request)

1. `POST /api/scans/frame` → `process_frame` in a worker thread.
2. Decode JPEG, reject <120×40 or >25 MP.
3. Average-hash (8×8) → `FrameDeduplicator` TTL cache. Repeats return `skipped`
   without OCR or stats changes.
4. `OcrEngine.recognize`:
   - resize, CLAHE, unsharp, deskew;
   - 2–3 binarised variants, Tesseract `ben+eng`, PSM 7;
   - line confidence + digit normalization + strict serial validation;
   - aggregate candidates, apply consensus rule.
5. Persist:
   - accepted → one transaction, duplicate check, insert bond + attempt;
   - uncertain → save JPEG under `database/captures/YYYY-MM-DD/`, insert attempt;
   - failed → insert attempt only.
6. Return the attempt, bond (if any) and fresh stats in one response.

The client updates the dashboard from `response.stats`, so it does not need a
second request to see the new count.

## Duplicate protection layers

| Layer | What it prevents |
| --- | --- |
| Client quality gate | Blurry/dark frames never reach OCR |
| Client frame hash (≤4 bits within 5 s) | Looping camera on the same bond |
| Server frame hash (TTL 2.5 s) | Two phones/clients sending the same view |
| OCR consensus | Saving low-confidence digits |
| `BEGIN IMMEDIATE` + `SELECT` | Two concurrent requests both seeing "not present" |
| `UNIQUE(serial)` | Any logic bug or bypass of the check |
| Duplicate attempt log | Auditing repeated presentations without losing the count |

## Why SQLite

Single user, local network, 2,000 rows. SQLite needs no service, survives
restarts, backs up as one file and is faster than a network database here. WAL
allows reads during writes; `busy_timeout=15s` plus short transactions avoids
"database is locked" under the camera's request rate.

## Why Tesseract

Offline-first is a hard requirement; cloud OCR would add latency, cost, network
dependency and privacy exposure. Tesseract 5 with `ben+eng` is installed on the
laptop. It is not perfect on Bengali bond numerals, which is why the system is
built around review rather than blind automation. `docs/OCR.md` records measured
accuracy and tuning.

## Frontend behaviour

- `useCamera` requests `facingMode: environment`, falls back to any camera, then
  enables continuous autofocus and torch if the track exposes capabilities.
- `quality.js` draws the guide rect from the same fractions used by the CSS
  overlay. Container aspect ratio is set from the video metadata so the crop maps
  exactly to what the user sees.
- The auto loop runs every 750 ms. It uploads only when quality passes, the frame
  differs from the last one, no request is in flight, no review is open and the
  cooldown has elapsed.
- The server returns `status`; the UI pauses for `uncertain`, toasts for
  `saved`/`duplicate`, and shows a hint for `failed`.
- Manual edits call `PATCH /api/bonds/{id}`; corrections are fetched per bond and
  shown in the modal.

## Error handling

- OCR unavailable → 503; dashboard shows "OCR unavailable" and still supports
  manual entry/export.
- Network loss → client catches fetch errors, shows an offline banner and retries
  on the next poll/window focus.
- Undecodable image → 400, no attempt row.
- Duplicate manual entry → 409 with the existing bond in the response.
- SQLite errors are logged in API responses only as a generic detail to avoid
  leaking paths to the network.

## Configuration and deployment

All settings are environment variables with sane defaults. The server can run
directly (`backend/run.py`), via `scripts/start.sh`, or in Docker (multi-stage
build: Node builds the UI, Python runs with Tesseract `ben+eng`). HTTPS is
provided by uvicorn with `certs/server.crt`/`server.key`; this is what makes
Android camera access work without an APK.

## Extension points

- **Other bond series**: change the three serial validation settings.
- **Better Bengali accuracy**: train/fine-tune a Tesseract model with your bond
  font, set `PBS_TESSDATA_DIR` to the new language data and `PBS_OCR_LANG` to it.
- **Native live preview**: add `@capacitor-community/camera-preview`, call
  `captureSample()` in the same loop and post the base64 to `/api/scans/frame`.
  No backend change needed.
- **Multi-user**: add authentication and per-user bond ownership; the DB and API
  are currently single-collection by design.
