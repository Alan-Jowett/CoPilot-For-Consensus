#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Setup script to extract public key from auth service
# This should be run after auth service is healthy

set -e

SECRETS_DIR="./secrets"
PUBLIC_KEY_FILE="$SECRETS_DIR/auth_service_public_key.pem"
AUTH_SERVICE_URL="${AUTH_SERVICE_URL:-http://localhost:8080/auth}"

echo "Extracting public key from auth service..."
echo "Auth service URL: $AUTH_SERVICE_URL"

# Wait for auth service to be available
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -sf "$AUTH_SERVICE_URL/.well-known/public_key.pem" > /dev/null 2>&1; then
        echo "Auth service is ready"
        break
    fi
    echo "Waiting for auth service... (attempt $((attempt + 1))/$max_attempts)"
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Auth service did not become ready after $max_attempts attempts"
    exit 1
fi

# Create secrets directory if it doesn't exist
mkdir -p "$SECRETS_DIR"

# Extract public key
echo "Downloading public key..."
if ! curl -sf "$AUTH_SERVICE_URL/.well-known/public_key.pem" > "$PUBLIC_KEY_FILE"; then
    echo "ERROR: Failed to download public key"
    exit 1
fi

if [ ! -f "$PUBLIC_KEY_FILE" ]; then
    echo "ERROR: Public key file was not created"
    exit 1
fi

# Verify it's a valid PEM file
if ! openssl pkey -pubin -in "$PUBLIC_KEY_FILE" -noout 2>/dev/null; then
    echo "ERROR: Downloaded file is not a valid PEM public key"
    rm -f "$PUBLIC_KEY_FILE"
    exit 1
fi

echo "✓ Public key successfully extracted and stored at: $PUBLIC_KEY_FILE"
echo ""
echo "To use JWKS endpoint instead, set GF_AUTH_JWT_JWKS_URL in docker-compose.infra.yml"
echo "and remove GF_AUTH_JWT_KEY_FILE setting"
