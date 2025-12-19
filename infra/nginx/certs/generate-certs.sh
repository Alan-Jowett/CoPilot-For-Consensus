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
echo "To enable TLS in the API Gateway, set in your .env file:"
echo "  GATEWAY_TLS_ENABLED=true"
echo ""
echo "Access the gateway via HTTPS:"
echo "  https://localhost:8443/"
echo ""
echo "Note: Browsers will show a security warning because this is a self-signed certificate."
echo "      This is expected for local development."
echo ""
