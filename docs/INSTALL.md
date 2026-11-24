# Installation

Target laptop: HP ZBook 15u G5, i7-8650U, 14 GB RAM, Ubuntu 24.04/26.04.
The app also runs on any Linux/macOS machine with Python 3.11+ and Node 18+.

## 1. System packages

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-ben
```

Verify both languages are visible:

```bash
tesseract --version
tesseract --list-langs
# eng
# ben
```

Python and Node:

```bash
sudo apt install -y python3-venv python3-pip nodejs npm
python3 --version   # 3.11+
node --version      # 18+
```

## 2. Project environment

From the project root:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
```

Build the React dashboard:

```bash
cd frontend
npm install
npm run build
cd ..
```

`backend` serves `frontend/dist` automatically. For development, use
`./scripts/dev.sh` instead (Vite on port 5173, API on 8000).

## 3. Certificate for phone camera access

Android Chrome exposes `getUserMedia` only in a secure context. `localhost` is
secure, a plain LAN IP is not. Generate a self-signed certificate with the
laptop's LAN IPs in the SAN:

```bash
./scripts/generate_cert.sh
```

Output:

```
certs/server.crt
certs/server.key
```

Start with HTTPS:

```bash
.venv/bin/python backend/run.py --ssl
```

or just:

```bash
./scripts/start.sh --ssl
```

The server prints all LAN addresses. Open `https://<laptop-ip>:8443` on the
phone and accept the warning once. Detailed phone steps:
[CAMERA.md](CAMERA.md).

## 4. Firewall and router

Allow the port on the laptop:

```bash
sudo ufw allow 8443/tcp    # HTTPS
sudo ufw allow 8000/tcp    # HTTP, if used on the laptop only
```

If the router has "AP isolation" / "client isolation" enabled, the phone cannot
reach the laptop. Disable it for the private Wi-Fi, or use the phone's hotspot
with the laptop connected to it. Verify from the phone's browser:
`https://<laptop-ip>:8443/api/health`.

## 5. Running

```bash
# HTTPS, phone + laptop (recommended)
./scripts/start.sh --ssl

# HTTP, laptop only
./scripts/start.sh

# custom port
PORT=9000 ./scripts/start.sh --ssl

# development with auto-reload + Vite HMR
./scripts/dev.sh
```

Open the dashboard:

- Laptop: `http://localhost:8000`
- Phone: `https://<laptop-ip>:8443`

## 6. Portable Tesseract (no sudo)

If you cannot install system packages, Tesseract can live inside the project.
The backend automatically looks in `.vendor/tesseract-local/usr/bin/tesseract`
and `.vendor/tesseract-local/usr/share/tesseract-ocr/5/tessdata`.

```bash
mkdir -p .vendor/tessdebs && cd .vendor/tessdebs

# Language data (small, architecture independent)
apt-get download tesseract-ocr-eng tesseract-ocr-ben

# Binary. If apt resolves to an ESM build that needs authentication, take the
# public archive build directly:
curl -fLO http://archive.ubuntu.com/ubuntu/pool/universe/t/tesseract/tesseract-ocr_5.5.0-1build1_amd64.deb

for f in *.deb; do dpkg-deb -x "$f" ../tesseract-local; done

# The binary links against libtesseract.so.5 / libleptonica.so.6. Check:
ldd ../tesseract-local/usr/bin/tesseract | grep -E "tesseract|lept"

../tesseract-local/usr/bin/tesseract --list-langs \
  --tessdata-dir ../tesseract-local/usr/share/tesseract-ocr/5/tessdata
```

If `libtesseract` or `libleptonica` are missing, install them system-wide
(`sudo apt install libtesseract5 libleptonica6`), or extract the matching `.deb`
files into `.vendor/tesseract-local` and start the server with:

```bash
LD_LIBRARY_PATH="$PWD/.vendor/tesseract-local/usr/lib/x86_64-linux-gnu" \
  ./scripts/start.sh --ssl
```

Override discovery explicitly if your paths differ:

```bash
PBS_TESSERACT_CMD=/opt/tesseract/bin/tesseract \
PBS_TESSDATA_DIR=/opt/tesseract/share/tessdata \
  .venv/bin/python backend/run.py --ssl
```

## 7. Docker

```bash
docker compose up --build
```

- Dashboard/API: `http://localhost:8000`
- Database: bind-mounted at `./database/prize_bonds.db`
- Exports: `./exports`
- Tesseract `ben+eng` is installed in the image.

For HTTPS in Docker, generate certs on the host and enable the 8443 mapping and
command in `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"
  - "8443:8443"
command: ["python", "backend/run.py", "--host", "0.0.0.0", "--port", "8443", "--ssl"]
```

## 8. Data and backups

| Path | Contents |
| --- | --- |
| `database/prize_bonds.db` | Bonds, scan attempts, duplicates, corrections |
| `database/captures/` | Frames kept for uncertain reads |
| `exports/` | Last 20 XLSX/CSV exports |
| `certs/` | HTTPS certificate and key |

Back up the single SQLite file for a complete copy of your collection:

```bash
sqlite3 database/prize_bonds.db ".backup database/backup_$(date +%F).db"
```

or simply copy it while the server is stopped.

Reset a test database (destructive):

```bash
rm database/prize_bonds.db
```

It is recreated on the next start.

## 9. Updating

```bash
git pull            # or unpack a new release over the old folder
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)
./scripts/start.sh --ssl
```

The schema uses `CREATE TABLE IF NOT EXISTS`; existing scans are preserved.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Tesseract binary not found` | Install `tesseract-ocr` or set `PBS_TESSERACT_CMD`; check `/api/health` |
| `/api/health` says OCR unavailable, `ben` missing | Install `tesseract-ocr-ben`, restart the server |
| Dashboard opens but camera says HTTPS required | Use the `https://` address, not `http://<ip>` |
| Phone cannot reach laptop | Same Wi-Fi, disable AP isolation, allow port 8443 in firewall |
| `ERR_CERT_AUTHORITY_INVALID` | Advanced → Proceed once; or use `mkcert` with its CA trusted on the phone |
| Camera permission denied permanently | Chrome → site settings → Camera → Allow, reload |
| OCR always returns `no serial` | Good light, fill the guide with the printed line, avoid glare; test with `scripts/ocr_image.py frame.jpg` |
| Exports are stale | Download again; a new timestamped file is generated per request |
| SQLite `database is locked` | Not expected; transactions use WAL + 15 s busy timeout. Stop duplicate server processes. |
