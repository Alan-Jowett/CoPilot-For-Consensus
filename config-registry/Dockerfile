# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared adapters
COPY adapters /app/adapters

# Install shared adapters
RUN cd /app/adapters && \
    python3 scripts/install_adapters.py

# Copy service files
COPY config-registry/requirements.txt .
COPY config-registry/main.py .
COPY config-registry/app ./app
COPY documents/schemas /app/documents/schemas

# Install service dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
