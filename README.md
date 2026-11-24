# Bangladesh Prize Bond Scanner

A local-first scanning system for Bangladesh Prize Bonds. Hold a bond's serial
number in front of the Vivo V21 rear camera; the laptop OCRs the frame, rejects
duplicates, stores the serial in SQLite and exports the collection to Excel.

Built for the real job: about **2,000 bonds**, no typing, no cloud, no internet.

```
Vivo V21 ──HTTPS/Wi-Fi──> FastAPI ──> OpenCV + Tesseract (ben+eng)
                              │
                              ├──> SQLite (unique serials, attempts, corrections)
                              └──> XLSX / CSV exports
```

## What it does

- **Automatic scanning** — live camera preview with a serial guide. Sharp frames
  are captured and sent without pressing a button. Identical frames are skipped
  on both the phone and the server.
- **Bengali + English OCR** — Tesseract `ben+eng`, Bengali/ASCII digit
  normalization and configurable 7-digit serial validation.
- **Never saves uncertainty silently** — a serial is auto-saved only when two
  independent binarisations agree (or one read is exceptionally confident and
  nothing contradicts it). Everything else appears in a review card.
- **Duplicate safety** — a SQLite `UNIQUE` constraint plus serialized
  `BEGIN IMMEDIATE` transactions make double-inserts impossible, even with
  concurrent requests. Duplicate attempts are counted separately.
- **Dashboard** — unique bonds, total scans, duplicates, failed OCR, remaining
  target, daily count, progress bar and recent scan history.
- **Correction history** — edit any saved serial; the old value is preserved.
- **Excel + CSV export** — serial, Bangla-digit serial, scan time, source,
  confidence and note. A summary sheet records totals. CSV includes a BOM so
  Excel opens Bengali text correctly.
- **Offline** — everything runs on the laptop over the local router. No external
  API, no telemetry.

## Quick start (Ubuntu laptop)

```bash
cd prize-bond-scanner

# OCR engine with Bengali language data
sudo apt install -y tesseract-ocr tesseract-ocr-ben

# Creates the venv, installs dependencies, builds the UI, makes a certificate,
# then serves HTTPS on port 8443 (HTTP on 8000 if you omit --ssl).
./scripts/start.sh --ssl
```

The terminal prints the LAN address, for example:

```
Phone:   https://172.16.0.2:8443   (same Wi-Fi)
```

On the Vivo V21 (Chrome, same Wi-Fi):

1. Open that `https://` address.
2. Accept the self-signed certificate warning once (Advanced → Proceed).
3. Tap **Start camera** and allow camera permission.
4. Hold the bond serial inside the guide. Auto scan saves clear reads.

Use `http://localhost:8000` for the dashboard on the laptop itself. Android
Chrome only allows camera access in a secure context, which is why the phone
uses HTTPS — see [docs/CAMERA.md](docs/CAMERA.md).

### Manual start

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)
./scripts/generate_cert.sh
.venv/bin/python backend/run.py --ssl        # or: --port 8000
```

## Daily workflow

1. Start the server from the laptop.
2. Open the dashboard on the phone, start the camera, switch **Auto scan** on.
3. Present bonds one by one. A green result means saved; an amber result means
   the read needs review or the serial is a duplicate.
4. For a review, correct the number in the card and tap **Save serial** — scanning
   is paused until the review is resolved.
5. At any time, download **Excel** or **CSV** from the sidebar or the API.

The dashboard survives restarts because all state lives in
`database/prize_bonds.db`. A copy of every export is written to `exports/`
(latest 20 kept).

## Project layout

```
prize-bond-scanner/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app + static frontend serving
│   │   ├── config.py          env configuration, Tesseract discovery
│   │   ├── ocr.py             OpenCV preprocessing + Tesseract consensus
│   │   ├── serials.py         Bengali digit normalization / validation
│   │   ├── scan_service.py    frame dedupe, atomic saves, stats, queries
│   │   ├── exports.py         XLSX / CSV generation
│   │   ├── db.py              SQLite schema and transactions
│   │   ├── schemas.py         request models
│   │   └── routers/           scan, bond, export and system routes
│   ├── run.py                 server entry point (HTTP/HTTPS)
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/                  React + Vite dashboard
│   ├── src/components/        camera, review, stats, history, modals
│   ├── src/hooks/useCamera.js
│   ├── src/lib/quality.js     guide crop, sharpness gate, frame hashing
│   └── capacitor.config.json  optional Android shell
├── database/                  SQLite database (runtime)
├── exports/                   generated XLSX/CSV copies (runtime)
├── certs/                     self-signed HTTPS certificate (runtime)
├── docs/                      installation, camera, OCR, API, tests
├── scripts/                   start, dev, certs, sample generation, OCR eval
├── tests/                     pytest suite + synthetic/real fixtures
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## How a scan becomes a row

1. The browser crops the area inside the guide frame, checks brightness /
   sharpness / contrast, hashes the frame and posts a JPEG to
   `POST /api/scans/frame`.
2. The backend rejects repeated fingerprints, then runs 2–3 Tesseract passes on
   independent binarisations (Otsu, grayscale, adaptive threshold).
3. Bengali digits are normalized to ASCII. Each read is validated against the
   serial pattern (default: 7 digits, optional 1–2 letter prefix, leading zeros
   preserved).
4. A candidate is auto-saved only if the winning serial is agreed by at least two
   variants and meets the confidence threshold (default 72), or if one pass is
   ≥ 94 and no other valid serial was seen.
5. The save, duplicate record or failed attempt is written in one transaction;
   the dashboard updates immediately. Low-confidence reads are stored as
   `uncertain` with the captured frame and await human confirmation.

## Configuration

All values are environment variables (see `backend/app/config.py`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `PBS_TARGET` | `2000` | Remaining-target calculation |
| `PBS_DB_PATH` | `database/prize_bonds.db` | SQLite file |
| `PBS_EXPORTS_DIR` | `exports` | Generated export copies |
| `PBS_CAPTURES_DIR` | `database/captures` | Frames saved for review |
| `PBS_OCR_LANG` | `ben+eng` | Tesseract languages |
| `PBS_AUTO_SAVE_CONFIDENCE` | `72` | Auto-save threshold with agreement |
| `PBS_SINGLE_VARIANT_CONFIDENCE` | `94` | One-pass auto-save threshold |
| `PBS_SERIAL_PATTERN` | `^[A-Z\u0985-\u09B9\u09DC-\u09DF]{0,2}\d{7}$` | Serial format validation |
| `PBS_MIN_SERIAL_DIGITS` / `PBS_MAX_SERIAL_DIGITS` | `7` / `7` | Digit count |
| `PBS_FRAME_DEDUPE_SECONDS` | `2.5` | Server-side repeated-frame window |
| `PBS_TESSERACT_CMD` | auto | Path to tesseract (local vendor supported) |
| `PBS_TESSDATA_DIR` | auto | Path to tessdata |
| `PBS_TIMEZONE` | `Asia/Dhaka` | Export timestamps |
| `PBS_MAX_UPLOAD_MB` | `12` | Frame size limit |
| `PBS_CORS_ORIGINS` | `*` | Allowed web origins |

If you collect a different bond series, adjust `PBS_SERIAL_PATTERN`,
`PBS_MIN_SERIAL_DIGITS` and `PBS_MAX_SERIAL_DIGITS` together.

## Tests

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

Latest run: **30 passed** (serial normalization, Bengali/English OCR safety,
concurrent duplicate inserts, API flow, manual corrections, 2,000-row export,
persistence).

OCR accuracy check on the included fixtures:

```bash
python scripts/evaluate_ocr.py --real
```

Last measured: **16/20 exact synthetic Bengali reads (80%)**, 9 correct
auto-saves, **0 wrong auto-saves**, average 700 ms per frame on an i7 laptop.
English digits are read exactly (4/4 test set). The included 512 px press photo
is too degraded and is deliberately refused — the safety behaviour working as
designed. Full details in [docs/OCR.md](docs/OCR.md) and
[docs/TESTING.md](docs/TESTING.md).

## Docker

```bash
docker compose up --build
# dashboard: http://localhost:8000
```

The image installs Tesseract with Bengali data and builds the frontend. Data is
bind-mounted to `./database` and `./exports`. HTTPS inside Docker is documented
in [docs/INSTALL.md](docs/INSTALL.md).

## Documentation

- [Installation](docs/INSTALL.md) — native, portable Tesseract, Docker, firewall
- [Camera & Android](docs/CAMERA.md) — HTTPS, Vivo V21, permissions, Capacitor
- [OCR pipeline](docs/OCR.md) — thresholds, accuracy, tuning with your samples
- [API reference](docs/API.md) — every endpoint with curl examples
- [Testing](docs/TESTING.md) — automated + browser end-to-end results, manual checklist
- [Architecture](docs/ARCHITECTURE.md) — schema, concurrency, design decisions

## Notes and limits

- This is a personal, single-household tool. Do not expose it to the public
  internet; there is no authentication.
- OCR accuracy depends on light, focus, print quality and the font used by the
  bond series. Validate 10 bonds with `scripts/evaluate_ocr.py` before a bulk
  run, and keep **Auto scan** off for the first few.
- The camera is controlled by the browser. Autofocus is automatic on the Vivo
  V21; tap-to-focus is not exposed to web apps. Use good light and fill the guide.
- A self-signed certificate triggers a browser warning once; accept it on your
  own device. For a warning-free setup, use `mkcert` as described in the camera
  guide.
- Back up `database/prize_bonds.db` (and `exports/`) regularly.
