# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

# Install rsync for archive fetching
RUN apt-get update && \
    apt-get install -y --no-install-recommends rsync && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared adapters first (storage before events to satisfy dependency)
COPY adapters/ /app/adapters/
RUN pip install --no-cache-dir /app/adapters/copilot_storage /app/adapters/copilot_events /app/adapters/copilot_reporting /app/adapters/copilot_config

# Install service dependencies
COPY ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY ingestion/app/ ./app/
COPY ingestion/*.py ./

CMD ["python", "main.py"]
