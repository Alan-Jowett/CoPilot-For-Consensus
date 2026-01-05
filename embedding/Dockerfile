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
    copilot_events \
    copilot_storage \
    copilot_vectorstore \
    copilot_metrics \
    copilot_reporting \
    copilot_schema_validation \
    copilot_logging \
    copilot_secrets \
    copilot_startup

# Install optional vectorstore backends with Qdrant and Azure AI Search support
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_vectorstore[qdrant,azure]

# Install PyTorch-based embedding backend for production
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e /app/adapters/copilot_embedding[sentencetransformers]

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
