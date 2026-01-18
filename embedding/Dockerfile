# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM pytorch/pytorch@sha256:11691e035a3651d25a87116b4f6adc113a27a29d8f5a6a583f8569e0ee5ff897

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
    copilot_embedding \
    copilot_config \
    copilot_message_bus \
    copilot_storage \
    copilot_vectorstore \
    copilot_metrics \
    copilot_error_reporting \
    copilot_schema_validation \
    copilot_logging \
    copilot_secrets \
    copilot_startup \
    copilot_event_retry

# Install all vectorstore backends (Qdrant, Azure AI Search, FAISS, InMemory)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_vectorstore[all]

# Install all embedding backends (SentenceTransformers, OpenAI, Azure OpenAI, HuggingFace, Mock)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_embedding[all]

# Copy schema files for validation
COPY docs/schemas /app/docs/schemas

# Install service dependencies with cache mount
COPY embedding/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy service code (last to maximize cache reuse)
COPY embedding/*.py ./
COPY embedding/app/ ./app/

CMD ["python", "main.py"]
