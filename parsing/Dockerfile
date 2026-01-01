# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

WORKDIR /app

# NOTE: If your environment uses SSL inspection or a custom CA, configure pip
# to use the correct CA certificate bundle instead of disabling TLS verification.
# Example: COPY your-ca-cert.crt /usr/local/share/ca-certificates/ && update-ca-certificates
# See: https://pip.pypa.io/en/stable/topics/configuration/

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py \
    copilot_config \
    copilot_events \
    copilot_storage \
    copilot_metrics \
    copilot_reporting \
    copilot_schema_validation \
    copilot_logging \
    copilot_secrets \
    copilot_startup

# Copy schema files for validation
COPY documents/schemas /app/documents/schemas

# Install service dependencies
COPY parsing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY parsing/app/ ./app/
COPY parsing/*.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
