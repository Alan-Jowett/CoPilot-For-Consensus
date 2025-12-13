# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python@sha256:158caf0e080e2cd74ef2879ed3c4e697792ee65251c8208b7afb56683c32ea6c

WORKDIR /app

# NOTE: If your environment uses SSL inspection or a custom CA, configure pip
# to use the correct CA certificate bundle instead of disabling TLS verification.
# See: https://pip.pypa.io/en/stable/topics/configuration/

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py --no-dev

# Copy schema files for validation
COPY documents/schemas /app/documents/schemas

# Copy requirements and install dependencies
COPY error-reporting/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY error-reporting/ .

# Expose port
EXPOSE 8081

# Run the application
CMD ["python", "main.py"]
