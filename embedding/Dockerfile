# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM pytorch/pytorch@sha256:11691e035a3651d25a87116b4f6adc113a27a29d8f5a6a583f8569e0ee5ff897

WORKDIR /app

# NOTE: If your environment uses SSL inspection or a custom CA, configure pip
# to use the correct CA certificate bundle instead of disabling TLS verification.
# Example: COPY your-ca-cert.crt /usr/local/share/ca-certificates/ && update-ca-certificates
# See: https://pip.pypa.io/en/stable/topics/configuration/

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py \
    copilot_embedding \
    copilot_config \
    copilot_events \
    copilot_storage \
    copilot_vectorstore \
    copilot_metrics \
    copilot_reporting

# Install optional vectorstore backend with Qdrant support
RUN pip install -e /app/adapters/copilot_vectorstore[qdrant]

# Install PyTorch-based embedding backend for production
RUN pip install -e /app/adapters/copilot_embedding[sentencetransformers]

# Copy schema files for validation
COPY documents/schemas /app/documents/schemas

# Install service dependencies
COPY embedding/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY embedding/*.py ./
COPY embedding/app/ ./app/

CMD ["python", "main.py"]
