<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Ollama GPU Support Setup Guide

This guide explains how to enable GPU acceleration for Ollama local LLM inference in Copilot-for-Consensus. GPU support can provide **10-100x faster inference** compared to CPU-only execution.

## Benefits

- **Faster inference**: 10-100x speedup for local LLM operations
- **Reduced latency**: Near real-time summarization for email threads
- **Better throughput**: Process more documents in parallel
- **Cost effective**: No cloud API costs while maintaining high performance

## Prerequisites

### Hardware Requirements

- **NVIDIA GPU** with CUDA support (GeForce, Quadro, Tesla, or RTX series)
- **Minimum 6GB VRAM** recommended for models like Mistral
- **8GB+ VRAM** recommended for larger models

### Software Requirements

#### Linux

1. **NVIDIA GPU Drivers** (version 470.x or newer)
   - Check installed version: `nvidia-smi`
   - Download from: https://www.nvidia.com/Download/index.aspx

2. **NVIDIA Container Toolkit**
   - Installation guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
   - Quick install (Ubuntu/Debian):
     ```bash
     curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
     curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
       sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
       sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
     sudo apt-get update
     sudo apt-get install -y nvidia-container-toolkit
     sudo nvidia-ctk runtime configure --runtime=docker
     sudo systemctl restart docker
     ```

3. **Docker** (version 19.03 or newer)
   - Docker with GPU support configured

#### Windows (WSL2)

1. **Windows 10/11** with WSL2 enabled
2. **NVIDIA GPU Drivers** for Windows (version 470.x or newer)
   - WSL2 uses the Windows GPU driver; no separate Linux driver needed
   - Download from: https://www.nvidia.com/Download/index.aspx
3. **Docker Desktop for Windows** with WSL2 backend
4. **NVIDIA Container Toolkit** in WSL2
   - Follow WSL2 setup guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html

## Enabling GPU Support

### Step 1: Verify GPU Access

Before enabling GPU support in Ollama, verify Docker can access your GPU:

```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

You should see output showing your GPU details. If this fails, revisit the prerequisites.

### Step 2: Enable GPU in docker-compose.yml

Edit `docker-compose.yml` and uncomment the `deploy` section under the `ollama` service:

```yaml
ollama:
  image: ollama/ollama:latest@sha256:6c76395793f40a5e78f120e880ca82c67e39eb908ad90eee8ce755535529d0ec
  ports:
    - "11434:11434"
  volumes:
    - ./ollama_models:/root/.ollama
  # Uncomment the deploy section below to enable GPU support
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  healthcheck:
    test: ["CMD-SHELL", "bash -lc 'echo > /dev/tcp/127.0.0.1/11434' "]
    interval: 10s
    timeout: 5s
    retries: 12
    start_period: 30s
  restart: unless-stopped
```

### Step 3: Restart Ollama Service

Restart the Ollama service to apply GPU configuration:

```bash
docker compose stop ollama
docker compose up -d ollama
```

Or restart all services:

```bash
docker compose down
docker compose up -d
```

### Step 4: Verify GPU Usage

Check if Ollama is using the GPU:

```bash
docker exec ollama nvidia-smi
```

You should see the Ollama process listed in the GPU processes table.

Alternatively, use the provided verification script:

**Linux/macOS/WSL2:**
```bash
./scripts/check_ollama_gpu.sh
```

**Windows PowerShell:**
```powershell
.\scripts\check_ollama_gpu.ps1
```

*Note: On Linux/macOS, if the script is not executable, run `chmod +x scripts/check_ollama_gpu.sh` first.*

Expected output:
- **With GPU**: `✓ GPU detected` + nvidia-smi output
- **Without GPU**: `✗ Running on CPU`

## Performance Comparison

Typical performance improvements with GPU acceleration:

| Model    | Hardware          | Tokens/sec | Speedup |
|----------|-------------------|------------|---------|
| Mistral  | CPU (8 cores)     | 2-5        | 1x      |
| Mistral  | GPU (RTX 3060)    | 50-100     | 20-50x  |
| Mistral  | GPU (RTX 4090)    | 150-200    | 50-100x |
| Llama2   | CPU (8 cores)     | 1-3        | 1x      |
| Llama2   | GPU (RTX 3060)    | 40-80      | 30-60x  |

*Note: Actual performance varies based on model size, prompt length, and hardware specifications.*

## Monitoring GPU Usage

### Real-time GPU Monitoring

Monitor GPU utilization in real-time:

```bash
watch -n 1 docker exec ollama nvidia-smi
```

### Prometheus Metrics

GPU metrics are automatically exposed by the cAdvisor service (port 8082) and scraped by Prometheus. View them in Grafana at http://localhost:3000.

Look for metrics like:
- `container_accelerator_memory_used_bytes`
- `container_accelerator_memory_total_bytes`
- `container_accelerator_duty_cycle`

## Troubleshooting

### GPU Not Detected

**Symptom**: `nvidia-smi` command fails inside container

**Solutions**:
1. Verify NVIDIA drivers are installed on host:
   ```bash
   nvidia-smi
   ```
2. Check NVIDIA Container Toolkit is installed:
   ```bash
   nvidia-ctk --version
   ```
3. Verify Docker runtime is configured:
   ```bash
   docker info | grep -i nvidia
   ```
4. Restart Docker daemon:
   ```bash
   sudo systemctl restart docker
   ```

### Out of Memory Errors

**Symptom**: Ollama fails with CUDA out-of-memory errors

**Solutions**:
1. **Use a smaller model**: Try `mistral:7b-instruct-q4_0` instead of full-precision models
2. **Reduce batch size**: Set `OLLAMA_MAX_LOADED_MODELS=1` in environment
3. **Free GPU memory**: Stop other GPU applications
4. **Use CPU offloading**: Ollama automatically offloads layers to CPU if GPU memory is insufficient

### Slow Performance Despite GPU

**Symptom**: GPU is detected but performance is not improved

**Solutions**:
1. **Verify GPU is actually being used**:
   ```bash
   docker exec ollama nvidia-smi
   ```
   Check GPU utilization % is non-zero during inference

2. **Check model is loaded on GPU**: Some quantized models may fall back to CPU
3. **Verify CUDA is available**: Check container logs for CUDA initialization messages
4. **Ensure model fits in VRAM**: Larger models may partially run on CPU

### Docker Compose Version Issues

**Symptom**: `deploy` section is ignored

**Solution**: Ensure you're using Docker Compose V2 (comes with Docker Desktop or `docker compose` command, not `docker-compose`). The `deploy` section requires Compose V2.

```bash
docker compose version
```

Expected: `Docker Compose version v2.x.x` or newer

## Disabling GPU Support

To revert to CPU-only execution:

1. Comment out the `deploy` section in `docker-compose.yml`
2. Restart the service:
   ```bash
   docker compose stop ollama
   docker compose up -d ollama
   ```

No data loss occurs - models stored in `./ollama_models` are preserved.

## Advanced Configuration

### Using Multiple GPUs

To use multiple GPUs, modify the `count` parameter:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all  # Use all available GPUs
          capabilities: [gpu]
```

Or specify a specific count:
```yaml
count: 2  # Use 2 GPUs
```

### GPU Memory Limits

Docker Compose does not support GPU memory limits. Use Ollama's built-in configuration instead:

```yaml
ollama:
  environment:
    - OLLAMA_MAX_LOADED_MODELS=1  # Limit concurrent models
```

### Using Specific GPU

To use a specific GPU (e.g., GPU 1 in a multi-GPU system):

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ['1']  # Use GPU 1
          capabilities: [gpu]
```

## References

- Ollama Docker documentation: https://hub.docker.com/r/ollama/ollama
- NVIDIA Container Toolkit: https://github.com/NVIDIA/nvidia-container-toolkit
- Docker Compose GPU support: https://docs.docker.com/compose/gpu-support/
- Ollama GitHub: https://github.com/ollama/ollama
- CUDA compatibility: https://docs.nvidia.com/deploy/cuda-compatibility/

## Support

For issues specific to:
- **Ollama**: https://github.com/ollama/ollama/issues
- **NVIDIA Container Toolkit**: https://github.com/NVIDIA/nvidia-container-toolkit/issues
- **This project**: https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues
