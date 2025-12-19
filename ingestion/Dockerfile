# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim@sha256:158caf0e080e2cd74ef2879ed3c4e697792ee65251c8208b7afb56683c32ea6c

# Install rsync for archive fetching
RUN apt-get update && \
    apt-get install -y --no-install-recommends rsync && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NOTE: If your environment uses SSL inspection or a custom CA, configure pip
# to use the correct CA certificate bundle instead of disabling TLS verification.
# Example: COPY your-ca-cert.crt /usr/local/share/ca-certificates/ && update-ca-certificates
# See: https://pip.pypa.io/en/stable/topics/configuration/

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py \
    copilot_auth \
    copilot_archive_fetcher \
    copilot_config \
    copilot_events \
    copilot_storage \
    copilot_logging \
    copilot_metrics \
    copilot_reporting \
    copilot_schema_validation \
    copilot_secrets

# Copy schema files for validation
COPY documents/schemas /app/documents/schemas

# Install service dependencies
COPY ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY ingestion/app/ ./app/
COPY ingestion/*.py ./

CMD ["python", "main.py"]
