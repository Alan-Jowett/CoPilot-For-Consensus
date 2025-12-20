#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Custom entrypoint script for NGINX API Gateway
# Conditionally enables HTTPS based on presence of TLS certificate secrets

set -e

CERT_SECRET="/run/secrets/gateway_tls_cert"
KEY_SECRET="/run/secrets/gateway_tls_key"
NGINX_CONF="/etc/nginx/nginx.conf"

# Check if TLS certificates are available via Docker secrets
if [ -f "$CERT_SECRET" ] && [ -f "$KEY_SECRET" ]; then
    echo "TLS certificates found in secrets - HTTPS will be enabled on port 8443"
    
    # Copy certificates from secrets to nginx certs directory
    mkdir -p /etc/nginx/certs
    cp "$CERT_SECRET" /etc/nginx/certs/server.crt
    cp "$KEY_SECRET" /etc/nginx/certs/server.key
    chmod 644 /etc/nginx/certs/server.crt
    chmod 600 /etc/nginx/certs/server.key
    
    # Update nginx.conf to uncomment the HTTPS server block
    sed -i 's/# __TLS_START__/__TLS_START__/g; s/# __TLS_END__/__TLS_END__/g' "$NGINX_CONF"
    sed -i '/__TLS_START__/,/__TLS_END__/s/^#//g' "$NGINX_CONF"
    sed -i '/__TLS_START__/d; /__TLS_END__/d' "$NGINX_CONF"
else
    echo "TLS certificates not found - HTTPS disabled, serving HTTP only on port 8080"
    echo "To enable HTTPS, provide 'gateway_tls_cert' and 'gateway_tls_key' secrets"
    
    # Remove the commented HTTPS server block from nginx.conf
    sed -i '/__TLS_START__/,/__TLS_END__/d' "$NGINX_CONF"
fi
