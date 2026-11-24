#!/usr/bin/env python3
"""Start the Prize Bond Scanner API and serve the built frontend.

Examples:
    python backend/run.py                 # http://0.0.0.0:8000
    python backend/run.py --ssl           # https://<lan-ip>:8443 (phone camera)
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


def lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ips.add(sock.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                ips.add(address)
    except OSError:
        pass
    return sorted(ips) or ["127.0.0.1"]


def main() -> int:
    project_root = BACKEND_DIR.parent
    parser = argparse.ArgumentParser(description="Prize Bond Scanner server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload for development")
    parser.add_argument("--ssl", action="store_true",
                        help="serve HTTPS using certs/server.crt + certs/server.key")
    parser.add_argument("--cert", default=str(project_root / "certs" / "server.crt"))
    parser.add_argument("--key", default=str(project_root / "certs" / "server.key"))
    args = parser.parse_args()

    ssl_kwargs = {}
    scheme = "http"
    if args.ssl:
        cert, key = Path(args.cert), Path(args.key)
        if not cert.is_file() or not key.is_file():
            print("Certificate files not found.\n"
                  f"  expected: {cert}\n            {key}\n"
                  "Run ./scripts/generate_cert.sh first.", file=sys.stderr)
            return 2
        ssl_kwargs = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
        scheme = "https"

    print("Prize Bond Scanner")
    print(f"  Local:   {scheme}://localhost:{args.port}")
    for ip in lan_ips():
        print(f"  Phone:   {scheme}://{ip}:{args.port}   (same Wi-Fi)")
    print("  API docs: /docs")
    if scheme == "http":
        print("  Note: Android Chrome needs HTTPS for camera access. "
              "Use --ssl for phone scanning.")
    print()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        **ssl_kwargs,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
