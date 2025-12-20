#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Generate self-signed certificates for local development and testing
# DO NOT use these certificates in production!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_FILE="$SCRIPT_DIR/server.crt"
KEY_FILE="$SCRIPT_DIR/server.key"

echo "=== Generating self-signed TLS certificates for local development ==="
echo ""
echo "WARNING: These certificates are for TESTING ONLY!"
echo "         Use valid CA-signed certificates in production."
echo ""

# Generate private key and self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -subj "/C=US/ST=State/L=City/O=CoPilot-For-Consensus/OU=Development/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:gateway,IP:127.0.0.1"

# Set appropriate permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo ""
echo "✓ Certificates generated successfully!"
echo ""
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"
echo ""
echo "To enable HTTPS in the API Gateway:"
echo "  1. Copy certificates to secrets directory:"
echo "     cp $CERT_FILE ../../secrets/gateway_tls_cert"
echo "     cp $KEY_FILE ../../secrets/gateway_tls_key"
echo "  2. Restart the gateway:"
echo "     docker compose up -d --build gateway"
echo ""
echo "The gateway will detect the secrets and automatically enable HTTPS on port 8443."
echo ""
echo "Access via:"
echo "  HTTP:  http://localhost:8080/"
echo "  HTTPS: https://localhost:8443/  (browser warning expected for self-signed certs)"
echo ""
