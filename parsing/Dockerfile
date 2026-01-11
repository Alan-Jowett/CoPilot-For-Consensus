# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim@sha256:aa9aac8eacc774817e2881238f52d983a5ea13d7f5a1dee479a1a1d466047951

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
    copilot_config \
    copilot_message_bus \
    copilot_storage \
    copilot_metrics \
    copilot_error_reporting \
    copilot_schema_validation \
    copilot_logging \
    copilot_secrets \
    copilot_startup

# Copy schema files for validation
COPY docs/schemas /app/docs/schemas

# Install service dependencies with cache mount
COPY parsing/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy service code (last to maximize cache reuse)
COPY parsing/app/ ./app/
COPY parsing/*.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
