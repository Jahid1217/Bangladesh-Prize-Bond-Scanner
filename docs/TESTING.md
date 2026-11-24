# Testing

## Run the automated suite

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

Latest result on the development machine (Ubuntu, Python 3.14, Tesseract 5.5,
OpenCV 5.1):

```
30 passed, 1 warning in 10.71s
```

The warning is Starlette's notice about its `TestClient` depending on `httpx`;
it does not affect functionality.

Tests use a temporary database (`tests/conftest.py`), so the real
`database/prize_bonds.db` is never touched.

## Test inventory

| File | Coverage |
| --- | --- |
| `tests/test_serials.py` | Bengali/Arabic digit normalization, leading zeros, prefixed serials, length/format rejection, candidate extraction from noisy lines, prize amounts ignored, safe repair suggestions |
| `tests/test_ocr.py` | English serials exact + auto-save, Bengali serials across 5 fonts/samples, **no wrong auto-save**, degraded real photo safety |
| `tests/test_api.py` | Health, camera frame save, identical-frame dedupe, duplicate detection, manual validation, correction history, history-row bond linking after corrections, listing/search/pagination, Bengali review confirmation, 8-thread concurrent duplicate insert, stats shape, persistence after new connection |
| `tests/test_exports.py` | XLSX headers/Bangla/leading zeros/note, Summary sheet, CSV BOM/Bangla, 2,000-row export under 15 s, filename/content-type |

Selected commands:

```bash
.venv/bin/python -m pytest tests/test_api.py -q
.venv/bin/python -m pytest -k "duplicate or concurrent" -q
.venv/bin/python -m pytest tests/test_ocr.py -q -s
```

## OCR measurements

```bash
python scripts/evaluate_ocr.py --real
```

Run on the included fixtures:

| Metric | Value |
| --- | --- |
| Synthetic Bengali samples | 20 |
| Exact reads | 16 (80%) |
| Auto-saved correct | 9 |
| Auto-saved wrong | 0 |
| Needs review | 9 |
| No serial | 2 |
| Average / max latency | ~700 ms / 855 ms |
| English test set | 4/4 exact, 3+ auto-saved |
| Real press photo (512×265) | correctly refused (`no_serial`) |

This is the honest state of Tesseract on Bengali bond digits: safe, but not
automatic for every frame. See [OCR.md](OCR.md) for thresholds and how to measure
your own bond samples.

## Browser end-to-end verification

The camera → OCR → SQLite → dashboard → export path was exercised in headless
Google Chrome using Chrome's fake camera with a synthetic bond video
(1280×720 Y4M, serial `7771234`). No physical Vivo V21 was attached to the
development host.

### Aligned serial frame

- Camera started through `getUserMedia` (1920×1080 stream).
- The client guide crop was uploaded automatically to `/api/scans/frame`.
- OCR returned `saved`, serial `7771234`, confidence 96%.
- The bond row appeared, the dashboard unique count increased to 2 (one earlier
  manual entry), and `GET /api/bonds` showed `source: "auto"`.
- The video looped and a second frame produced `duplicate`; no second bond row
  was created and the duplicate was counted.
- Scan history returned both attempts with `bond_id` for editing.
- Zero browser console errors or page errors.

### Misaligned / blurred frame

- With the serial partially outside the guide, OCR returned `uncertain` with a
  low-confidence candidate (54%).
- The UI opened the review card, scanning paused, and the captured frame was
  stored and served from `/api/scans/{id}/image`.
- No bond row was created. This is the core safety property.

### Manual entry and responsiveness

- Typed `7654321` in the manual form → `POST /api/bonds` 200, toast "Saved
  7654321", unique counter updated.
- Duplicate manual entry returns 409 and a field error in the UI.
- Opened a saved scan row → **Correct serial** modal, changed `7771234` to
  `7771235` → modal closed, "Serial corrected" toast, `corrections` contained
  `7771234 → 7771235`, and the history row remained editable via `bond_id`.
- At 390×844 (mobile viewport): `scrollWidth === innerWidth` (no horizontal
  overflow) and the stats grid resolved to two columns.
- At 1400×1000 the dashboard rendered six stat cards plus the progress bar and
  both columns with no console errors.

### Export verification

Downloaded from the live server after the browser scans:

- XLSX contained sheets `Prize Bonds` and `Summary`.
- Header row: `Serial Number`, `সিরিয়াল (বাংলা)`, `Scanned At`, `Source`,
  `Confidence (%)`, `Note`.
- Serial `7771234` present with Bangla column `৭৭৭১২৩৪`, source `auto`,
  confidence 96, timestamp in Asia/Dhaka.
- CSV starts with the UTF-8 BOM; Bengali headers and values decode correctly.
- Copies were written to `exports/`.

## Performance

Measured with 2,000 bonds in a temporary database:

| Operation | Time |
| --- | --- |
| Dashboard stats query (`/api/stats`) | 1.7 ms |
| XLSX generation (2,000 rows, two sheets) | 804 ms |
| CSV generation | 39 ms |
| OCR per crop | ~700 ms average |
| SQLite duplicate-race test | 8 concurrent requests → 1 saved, 7 duplicates |

At ~1.4 s per accepted bond (capture cooldown + OCR), 2,000 bonds is roughly
45–60 minutes of scanning including handling time.

## Manual checklist for the real Vivo V21

These require the physical phone and cannot be fully automated here:

- [ ] Open `https://<laptop-ip>:8443`, accept the certificate warning.
- [ ] Chrome camera permission granted; preview appears within 3 s.
- [ ] Autofocus settles on the serial at 15–25 cm in normal room light.
- [ ] Auto scan saves a clear 7-digit serial without pressing a button.
- [ ] Moving to the next bond scans it (no stuck frame).
- [ ] Re-presenting a saved bond triggers Duplicate, not a new row.
- [ ] Deliberately blurring the frame produces Review/no-serial, not a wrong save.
- [ ] Correcting a review serial stores it and appears in history.
- [ ] Torch button works if the browser exposes torch control.
- [ ] Screen lock/rotation does not leave the camera stream running.
- [ ] Dashboard remains usable in portrait; no horizontal scrolling.
- [ ] Stop the server and confirm the UI shows "Backend offline" gracefully.
- [ ] Restart the server and confirm all scans persist.
- [ ] Export XLSX from a laptop browser and open it in LibreOffice; Bengali
      renders and leading zeros are preserved.
- [ ] Run the full 2,000-bond batch, then export and verify the count equals the
      dashboard unique count.

## 2,000-bond load test procedure

Before a real batch:

1. Generate 2,000 synthetic strips with `python scripts/generate_samples.py
   --count 2000 --out /tmp/load` (takes a few minutes and disk space).
2. Or load rows directly:
   ```bash
   PBS_DB_PATH=/tmp/load.db PYTHONPATH=backend .venv/bin/python - <<'PY'
   from app.db import db, utc_now

   db.init()
   now = utc_now()
   rows = [(f"9{i:06d}", now, now) for i in range(1, 2001)]
   with db.transaction(immediate=True) as conn:
       conn.executemany(
           """INSERT INTO bonds
              (serial, raw_text, source, confidence, note, created_at, updated_at)
              VALUES (?, NULL, 'manual', NULL, NULL, ?, ?)""",
           rows,
       )
   print("inserted", len(rows))
   PY
   ```
3. Check `/api/stats` and export timings; both are covered by the automated
   2,000-row test.

## Offline / restart checks

- Scanning works with the router's internet connection unplugged; only the LAN
  and the laptop are needed.
- All state is in SQLite; restarting Uvicorn and reopening the phone page keeps
  bonds, duplicates, failures and corrections.
- No third-party service is contacted at runtime (verified by code review: only
  local API calls; fonts and Tesseract are local).

## Known verification gaps

- No physical Android device or real Vivo V21 camera in the development host;
  browser tests use Chrome's fake capture device.
- The only public real bond image found is 512 px wide, too low-resolution for
  Bengali OCR; it is used as a "must refuse" test. Real camera-resolution samples
  are needed to calibrate `PBS_AUTO_SAVE_CONFIDENCE` on the user's actual bonds.
- The Capacitor Android shell is configured and documented but no APK was built
  in this environment (no Android SDK). The native camera adapter is a single-shot
  fallback; live auto scanning is the browser HTTPS path.
- Docker image build was not executed in this environment. The Dockerfile and
  compose file are provided; `docker compose up --build` is the verification
  command on a machine with Docker.
