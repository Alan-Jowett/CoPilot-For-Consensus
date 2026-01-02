# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Authentication Service Dockerfile
# Single-stage build aligned with other services

FROM python:3.11-slim@sha256:aa9aac8eacc774817e2881238f52d983a5ea13d7f5a1dee479a1a1d466047951

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
    copilot_secrets

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
COPY documents/schemas ./documents/schemas

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health').read()" || exit 1

CMD ["python", "main.py"]
