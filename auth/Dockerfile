# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Authentication Service Dockerfile
# Multi-stage build for production-ready container

FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY auth/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Ensure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Install adapters (will be mounted as volumes in docker-compose)
# For standalone builds, copy and install adapters
COPY adapters/copilot_auth /tmp/copilot_auth
COPY adapters/copilot_logging /tmp/copilot_logging
COPY adapters/copilot_metrics /tmp/copilot_metrics

RUN pip install --no-cache-dir /tmp/copilot_auth /tmp/copilot_logging /tmp/copilot_metrics && \
    rm -rf /tmp/copilot_*

# Copy application code
COPY auth/app ./app
COPY auth/main.py .
COPY auth/config ./config

# Create non-root user
RUN useradd -m -u 1000 authuser && \
    chown -R authuser:authuser /app

USER authuser

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8090/health').raise_for_status()" || exit 1

# Run the service
CMD ["python", "main.py"]
