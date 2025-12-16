# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Script to check if Ollama is using GPU acceleration

Write-Host "Checking Ollama GPU status..."
Write-Host ""

$result = docker exec ollama nvidia-smi 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host $result
    Write-Host ""
    Write-Host "✓ GPU detected and accessible by Ollama" -ForegroundColor Green
    Write-Host ""
    Write-Host "GPU is available for accelerated inference!"
    exit 0
} else {
    Write-Host "✗ Running on CPU (GPU not detected)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To enable GPU support:"
    Write-Host "1. Ensure NVIDIA drivers and nvidia-container-toolkit are installed"
    Write-Host "2. Uncomment the 'deploy' section in docker-compose.yml under 'ollama' service"
    Write-Host "3. Restart the service: docker compose restart ollama"
    Write-Host ""
    Write-Host "See documents/OLLAMA_GPU_SETUP.md for detailed setup instructions"
    exit 1
}
