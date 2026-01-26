#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Substitute environment variables in nginx.conf template
# This allows the same configuration to work for both Docker Compose and Azure Container Apps
# by using different backend URL patterns per deployment environment.

set -e

# Set defaults for Docker Compose if not provided
export REPORTING_BACKEND=${REPORTING_BACKEND:-http://reporting:8080/}
export AUTH_BACKEND=${AUTH_BACKEND:-http://auth:8090/}
export INGESTION_BACKEND=${INGESTION_BACKEND:-http://ingestion:8001/}
export UI_BACKEND=${UI_BACKEND:-http://ui:80/}
# GRAFANA_BACKEND is optional (Docker Compose only, must be set explicitly)

# Diagnostics toggles
# CFC_GATEWAY_GZIP: "on" (default) or "off" to compare compressed vs uncompressed responses
# CFC_GATEWAY_LOG_RESPONSES: "1"/"true"/"on"/"yes" to emit response-focused access logs
# CFC_GATEWAY_ERROR_LOG_LEVEL: "warn" (default), "info", or "debug" for deeper protocol debugging
export CFC_GATEWAY_GZIP=${CFC_GATEWAY_GZIP:-on}
export CFC_GATEWAY_LOG_RESPONSES=${CFC_GATEWAY_LOG_RESPONSES:-0}
export CFC_GATEWAY_ERROR_LOG_LEVEL=${CFC_GATEWAY_ERROR_LOG_LEVEL:-warn}

echo "Configuring NGINX with backend URLs:"
echo "  REPORTING_BACKEND=$REPORTING_BACKEND"
echo "  AUTH_BACKEND=$AUTH_BACKEND"
echo "  INGESTION_BACKEND=$INGESTION_BACKEND"
if [ -n "$GRAFANA_BACKEND" ]; then
  echo "  GRAFANA_BACKEND=$GRAFANA_BACKEND (optional, Docker Compose only)"
fi
echo "  UI_BACKEND=$UI_BACKEND"
echo "  CFC_GATEWAY_GZIP=$CFC_GATEWAY_GZIP"
echo "  CFC_GATEWAY_LOG_RESPONSES=$CFC_GATEWAY_LOG_RESPONSES"
echo "  CFC_GATEWAY_ERROR_LOG_LEVEL=$CFC_GATEWAY_ERROR_LOG_LEVEL"

# Verify template file exists
if [ ! -f /etc/nginx/nginx.conf.template ]; then
  echo "ERROR: Template file /etc/nginx/nginx.conf.template not found"
  exit 1
fi

# Substitute environment variables in the nginx configuration
# Note: GRAFANA_BACKEND is optional (Docker Compose only)
if ! envsubst '${REPORTING_BACKEND} ${AUTH_BACKEND} ${INGESTION_BACKEND} ${GRAFANA_BACKEND} ${UI_BACKEND} ${CFC_GATEWAY_GZIP} ${CFC_GATEWAY_LOG_RESPONSES} ${CFC_GATEWAY_ERROR_LOG_LEVEL}' \
  < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf.tmp; then
  echo "ERROR: Failed to substitute environment variables"
  exit 1
fi

# Conditionally remove Grafana block if GRAFANA_BACKEND is not set
if [ -z "$GRAFANA_BACKEND" ]; then
  echo "GRAFANA_BACKEND not set; removing Grafana location block from config"
  # Use explicit temp file for portability (macOS BSD sed requires -i'' syntax)
  sed '/__GRAFANA_BLOCK_START__/,/__GRAFANA_BLOCK_END__/d' /etc/nginx/nginx.conf.tmp > /etc/nginx/nginx.conf.grafana-filtered
  mv /etc/nginx/nginx.conf.grafana-filtered /etc/nginx/nginx.conf.tmp
fi

mv /etc/nginx/nginx.conf.tmp /etc/nginx/nginx.conf

# Verify output file was created and is not empty
if [ ! -s /etc/nginx/nginx.conf ]; then
  echo "ERROR: Generated nginx.conf is missing or empty"
  exit 1
fi

echo "NGINX configuration generated successfully"
