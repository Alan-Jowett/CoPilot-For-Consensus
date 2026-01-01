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
export GRAFANA_BACKEND=${GRAFANA_BACKEND:-http://grafana:3000}
export UI_BACKEND=${UI_BACKEND:-http://ui:80/}

echo "Configuring NGINX with backend URLs:"
echo "  REPORTING_BACKEND=$REPORTING_BACKEND"
echo "  AUTH_BACKEND=$AUTH_BACKEND"
echo "  INGESTION_BACKEND=$INGESTION_BACKEND"
echo "  GRAFANA_BACKEND=$GRAFANA_BACKEND"
echo "  UI_BACKEND=$UI_BACKEND"

# Substitute environment variables in the nginx configuration
envsubst '${REPORTING_BACKEND} ${AUTH_BACKEND} ${INGESTION_BACKEND} ${GRAFANA_BACKEND} ${UI_BACKEND}' \
  < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

echo "NGINX configuration generated successfully"
