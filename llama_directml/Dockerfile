# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# DirectML-enabled llama.cpp server with AMD GPU support
# Uses CLBlast for GPU acceleration via DirectML on Windows/WSL2

FROM python:3.11-slim

# Install system dependencies for OpenCL and CLBlast
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    ocl-icd-opencl-dev \
    clblast \
    libclblast-dev \
    opencl-headers \
    && rm -rf /var/lib/apt/lists/*

# Set up OpenCL ICD loader to find GPU devices
RUN mkdir -p /etc/OpenCL/vendors && \
    echo "libamdocl64.so" > /etc/OpenCL/vendors/amdocl64.icd

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    requests==2.31.0 \
    prometheus-client==0.19.0

# Build llama-cpp-python with CLBlast support
# Force rebuild from source with CLBlast enabled
ENV CMAKE_ARGS="-DLLAMA_CLBLAST=on"
ENV FORCE_CMAKE=1

RUN pip install --no-cache-dir --force-reinstall --no-binary :all: llama-cpp-python==0.2.27

# Create model directory
RUN mkdir -p /models

# Copy server script
COPY server.py /app/server.py

# Expose port
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/health').read()"

# Run server
CMD ["python", "-u", "server.py"]
