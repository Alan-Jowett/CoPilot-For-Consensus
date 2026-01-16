# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.14-slim@sha256:1f741aef81d09464251f4c52c83a02f93ece0a636db125d411bd827bf381a763

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
# Use BuildKit cache mount for pip cache to speed up rebuilds
COPY adapters/ /app/adapters/
RUN --mount=type=cache,target=/root/.cache/pip \
    python /app/adapters/scripts/install_adapters.py \
    copilot_archive_store \
    copilot_auth \
    copilot_archive_fetcher \
    copilot_config \
    copilot_message_bus \
    copilot_storage \
    copilot_logging \
    copilot_metrics \
    copilot_error_reporting \
    copilot_schema_validation \
    copilot_secrets

# Copy schema files for validation
COPY docs/schemas /app/docs/schemas

# Install service dependencies with cache mount
COPY ingestion/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy service code (last to maximize cache reuse)
COPY ingestion/app/ ./app/
COPY ingestion/*.py ./

CMD ["python", "main.py"]
