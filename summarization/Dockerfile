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
RUN python /app/adapters/scripts/install_adapters.py --no-dev

# Copy schema files for validation
COPY documents/schemas /app/documents/schemas

# Install service dependencies
COPY summarization/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY summarization/app/ ./app/
COPY summarization/*.py ./

# Expose port for health endpoint
EXPOSE 8000

CMD ["python", "main.py"]
