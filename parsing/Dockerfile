# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

WORKDIR /app

# Install shared SDK first
COPY ../sdk/ /app/sdk/
RUN pip install --no-cache-dir \
    /app/sdk/copilot_events \
    /app/sdk/copilot_storage \
    /app/sdk/copilot_metrics \
    /app/sdk/copilot_reporting \
    /app/sdk/copilot_logging

# Install service dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY app/ ./app/
COPY *.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
