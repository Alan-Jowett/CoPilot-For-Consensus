# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
# NOTE: If your environment uses SSL inspection or a custom CA, configure pip
# to use the correct CA certificate bundle instead of disabling TLS verification.
# See: https://pip.pypa.io/en/stable/topics/configuration/
COPY error-reporting/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY error-reporting/ .

# Expose port
EXPOSE 8081

# Run the application
CMD ["python", "main.py"]
