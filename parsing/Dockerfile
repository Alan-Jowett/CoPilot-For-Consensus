# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

WORKDIR /app

# Copy adapters and schemas
COPY ../adapters/ /app/adapters/
COPY requirements.txt .
COPY ../documents/schemas /app/documents/schemas

RUN pip install --no-cache-dir -r requirements.txt
RUN python /app/adapters/scripts/install_adapters.py --no-dev

# Copy service code
COPY app/ ./app/
COPY *.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
