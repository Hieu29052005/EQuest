#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${ROOT_DIR}/certs"

mkdir -p "${CERT_DIR}"

if [[ -f "${CERT_DIR}/cert.pem" && -f "${CERT_DIR}/key.pem" ]]; then
  echo "[certs] Existing dev cert found, skipping generation."
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "${CERT_DIR}/key.pem" -out "${CERT_DIR}/cert.pem" \
  -days 365 -subj "/CN=EQuest Dev Signer" \
  -addext "keyUsage=digitalSignature" \
  -addext "extendedKeyUsage=emailProtection"

echo "[certs] Wrote ${CERT_DIR}/cert.pem and ${CERT_DIR}/key.pem"
echo "[certs] NOTE: dev self-signed cert — NOT trusted by public platforms."
