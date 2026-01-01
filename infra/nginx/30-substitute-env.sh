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
export GRAFANA_BACKEND=${GRAFANA_BACKEND:-http://grafana:3000/}
export UI_BACKEND=${UI_BACKEND:-http://ui:80/}

echo "Configuring NGINX with backend URLs:"
echo "  REPORTING_BACKEND=$REPORTING_BACKEND"
echo "  AUTH_BACKEND=$AUTH_BACKEND"
echo "  INGESTION_BACKEND=$INGESTION_BACKEND"
echo "  GRAFANA_BACKEND=$GRAFANA_BACKEND"
echo "  UI_BACKEND=$UI_BACKEND"

# Verify template file exists
if [ ! -f /etc/nginx/nginx.conf.template ]; then
  echo "ERROR: Template file /etc/nginx/nginx.conf.template not found"
  exit 1
fi

# Substitute environment variables in the nginx configuration
if ! envsubst '${REPORTING_BACKEND} ${AUTH_BACKEND} ${INGESTION_BACKEND} ${GRAFANA_BACKEND} ${UI_BACKEND}' \
  < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf; then
  echo "ERROR: Failed to substitute environment variables"
  exit 1
fi

# Verify output file was created and is not empty
if [ ! -s /etc/nginx/nginx.conf ]; then
  echo "ERROR: Generated nginx.conf is missing or empty"
  exit 1
fi

echo "NGINX configuration generated successfully"
