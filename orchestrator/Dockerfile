# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

FROM python:3.11-slim

WORKDIR /app

# Configure pip to trust PyPI (needed for environments with SSL inspection)
RUN pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org"

# Install shared adapters in dependency order using centralized script
COPY adapters/ /app/adapters/
RUN python /app/adapters/scripts/install_adapters.py --no-dev

# Install service dependencies
COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY orchestrator/*.py ./

CMD ["python", "main.py"]
