# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.14-slim@sha256:9b81fe9acff79e61affb44aaf3b6ff234392e8ca477cb86c9f7fd11732ce9b6a

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
    copilot_summarization \
    copilot_config \
    copilot_message_bus \
    copilot_storage \
    copilot_vectorstore \
    copilot_metrics \
    copilot_event_retry \
    copilot_error_reporting \
    copilot_schema_validation \
    copilot_logging \
    copilot_secrets \
    copilot_startup

# Install all vectorstore backends (Qdrant, Azure AI Search, FAISS, InMemory)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_vectorstore[all]

# Install all LLM backends (OpenAI, Azure OpenAI, Local, LlamaCpp, Mock)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_summarization[all]

# Copy schema files for validation
COPY docs/schemas /app/docs/schemas

# Install service dependencies with cache mount
COPY summarization/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy service code (last to maximize cache reuse)
COPY summarization/app/ ./app/
COPY summarization/*.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
