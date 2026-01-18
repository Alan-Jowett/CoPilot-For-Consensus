# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Authentication Service Dockerfile
# Single-stage build aligned with other services

FROM python:3.14-slim@sha256:9b81fe9acff79e61affb44aaf3b6ff234392e8ca477cb86c9f7fd11732ce9b6a

WORKDIR /app

# Install shared adapters in dependency order using centralized script
# Use BuildKit cache mount for pip cache to speed up rebuilds
COPY adapters/ /app/adapters/
RUN --mount=type=cache,target=/root/.cache/pip \
    python /app/adapters/scripts/install_adapters.py \
    copilot_auth \
    copilot_config \
    copilot_logging \
    copilot_metrics \
    copilot_schema_validation \
    copilot_secrets \
    copilot_storage

# Install Azure Key Vault dependencies for copilot-secrets
# Required for production deployments that use Azure Key Vault for secret management
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e "/app/adapters/copilot_secrets[azure]"

# Install service dependencies with cache mount
COPY auth/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy service code (last to maximize cache reuse)
COPY auth/app ./app
COPY auth/main.py .

# Copy schema configuration
COPY docs/schemas ./docs/schemas

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health').read()" || exit 1

CMD ["python", "main.py"]
