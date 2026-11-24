#!/usr/bin/env bash
# Generate a self-signed certificate so Android Chrome allows camera access
# over the local network (getUserMedia requires a secure context).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/certs"
mkdir -p "$CERT_DIR"

IPS=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.' || true)
SAN="DNS:localhost,IP:127.0.0.1"
for ip in $IPS; do
  SAN="$SAN,IP:$ip"
done

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -days 825 \
  -subj "/CN=prize-bond-scanner.local" \
  -addext "subjectAltName=$SAN" \
  >/dev/null 2>&1

chmod 600 "$CERT_DIR/server.key"
echo "Certificate created:"
echo "  $CERT_DIR/server.crt"
echo "  $CERT_DIR/server.key"
echo
echo "SAN: $SAN"
echo "Open https://<laptop-ip>:8443 on the phone and accept the certificate warning once."
