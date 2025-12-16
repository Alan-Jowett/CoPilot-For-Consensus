#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Script to check if Ollama is using GPU acceleration

set -e

echo "Checking Ollama GPU status..."
echo ""

if docker exec ollama nvidia-smi 2>/dev/null; then
    echo ""
    echo "✓ GPU detected and accessible by Ollama"
    echo ""
    echo "GPU is available for accelerated inference!"
    exit 0
else
    echo "✗ Running on CPU (GPU not detected)"
    echo ""
    echo "To enable GPU support:"
    echo "1. Ensure NVIDIA drivers and nvidia-container-toolkit are installed"
    echo "2. Uncomment the 'deploy' section in docker-compose.yml under 'ollama' service"
    echo "3. Restart the service: docker compose restart ollama"
    echo ""
    echo "See documents/OLLAMA_GPU_SETUP.md for detailed setup instructions"
    exit 1
fi
