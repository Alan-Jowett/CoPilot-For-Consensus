#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Custom entrypoint script for NGINX API Gateway
# Uses provided TLS certificates or generates self-signed ones

CERT_PATH="/etc/nginx/certs/server.crt"
KEY_PATH="/etc/nginx/certs/server.key"
NGINX_CONF="/etc/nginx/nginx.conf"
ENABLE_INTERNAL_TLS="${ENABLE_INTERNAL_TLS:-true}"

# Optional internal TLS (not needed when ACA terminates HTTPS and forwards HTTP)
if [ "$ENABLE_INTERNAL_TLS" = "true" ]; then
    # Create certs directory
    mkdir -p "$(dirname "$CERT_PATH")"

    # Check if TLS certificates are available (from bind mount or Docker secrets)
    if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
        echo "TLS certificates not found - generating self-signed certificates..."

        # Generate self-signed certificate (valid for 365 days)
        openssl req -x509 -newkey rsa:2048 \
            -keyout "$KEY_PATH" \
            -out "$CERT_PATH" \
            -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Copilot-for-Consensus/CN=localhost" 2>&1

        if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
            echo "✓ Self-signed certificates generated successfully"
            echo "  Certificate: $CERT_PATH"
            echo "  Private key: $KEY_PATH"
        else
            echo "ERROR: Failed to generate certificates"
            exit 1
        fi
    else
        echo "✓ TLS certificates found"
    fi

    # Set proper permissions (skip if read-only mount)
    # Try to chmod; if it fails, it's a read-only mount, which is fine
    chmod 600 "$KEY_PATH" 2>/dev/null || true
    chmod 644 "$CERT_PATH" 2>/dev/null || true

    # Configure nginx for HTTPS
    echo "Configuring nginx for HTTPS on port 8443..."
    sed -i 's/# __TLS_START__/__TLS_START__/g; s/# __TLS_END__/__TLS_END__/g' "$NGINX_CONF"
    sed -i '/__TLS_START__/,/__TLS_END__/s/^#//g' "$NGINX_CONF"
    sed -i '/__TLS_START__/d; /__TLS_END__/d' "$NGINX_CONF"
else
    echo "ENABLE_INTERNAL_TLS is false; serving HTTP on port 8080 with ACA-managed TLS termination."
fi

echo "✓ Configuration complete - starting nginx"
