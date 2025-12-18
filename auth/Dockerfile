# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Authentication Service Dockerfile
# Single-stage build aligned with other services

FROM python:3.11-slim@sha256:158caf0e080e2cd74ef2879ed3c4e697792ee65251c8208b7afb56683c32ea6c

WORKDIR /app

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py \
    copilot_auth \
    copilot_config \
    copilot_logging \
    copilot_metrics \
    copilot_secrets

# Install service dependencies
COPY auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
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
