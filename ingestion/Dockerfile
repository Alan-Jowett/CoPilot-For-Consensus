# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

# Install rsync for archive fetching
RUN apt-get update && \
    apt-get install -y --no-install-recommends rsync && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared SDK first (storage before events to satisfy dependency)
COPY sdk/ /app/sdk/
RUN pip install --no-cache-dir /app/sdk/copilot_storage /app/sdk/copilot_events

# Install service dependencies
COPY ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY ingestion/app/ ./app/
COPY ingestion/*.py ./

CMD ["python", "main.py"]
