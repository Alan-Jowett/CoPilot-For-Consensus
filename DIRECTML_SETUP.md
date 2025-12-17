# DirectML GPU Support Setup Guide

This guide explains how to enable AMD/Intel GPU acceleration for LLM inference using DirectML on Windows/WSL2.

## Overview

**DirectML** (DirectX Machine Learning) provides GPU acceleration for machine learning workloads on Windows. This implementation uses:

- **llama-cpp-python**: Python bindings for llama.cpp with GGUF model support
- **CLBlast**: OpenCL BLAS library that leverages DirectML for GPU acceleration
- **WSL2**: Windows Subsystem for Linux 2 with GPU passthrough via `/dev/dxg`

## Supported Hardware

| GPU Type | Support | Performance | Notes |
|----------|---------|-------------|-------|
| AMD Radeon (RX 6000/7000) | ✅ Excellent | 40-70 tok/s | Best performance |
| AMD Integrated (780M, etc.) | ✅ Good | 15-25 tok/s | Limited by VRAM |
| Intel Arc | ✅ Good | 20-40 tok/s | Tested on Arc A770 |
| Intel Integrated | ✅ Basic | 10-20 tok/s | Limited by VRAM |
| NVIDIA | ✅ Works | 30-50 tok/s | CUDA is faster, use Ollama instead |

## Prerequisites

### 1. Windows 11 with WSL2

```powershell
# Check Windows version (must be Windows 11 or Windows 10 22H2+)
winver

# Enable WSL2 if not already enabled
wsl --install

# Set WSL2 as default
wsl --set-default-version 2
```

### 2. GPU Drivers

**AMD GPU**:
- Install [AMD Adrenalin Software](https://www.amd.com/en/support) (latest version)
- Ensure driver version is 22.20.0 or newer

**Intel GPU**:
- Install [Intel Graphics Driver](https://www.intel.com/content/www/us/en/download-center/home.html)
- Ensure driver version supports DirectX 12

### 3. Verify WSL2 GPU Access

```powershell
# Check if /dev/dxg exists (WSL2 GPU device)
wsl -e bash -c "ls -la /dev/dxg"

# Should output: crw-rw-rw- 1 root root 10, 126 Dec 17 02:00 /dev/dxg
```

If `/dev/dxg` doesn't exist:
1. Update WSL: `wsl --update`
2. Restart WSL: `wsl --shutdown` then reopen
3. Verify GPU drivers are installed on Windows

### 4. Docker Desktop

- Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- Enable WSL2 backend: Settings → General → "Use the WSL 2 based engine"
- Enable GPU support: Settings → Resources → WSL Integration → Enable for your distro

### 5. Download LLM Model

Download the Mistral 7B Instruct model (GGUF format):

```powershell
# Create model directory
mkdir llama_models

# Download model (choose one method):

# Method 1: Using wget in WSL
wsl wget -P llama_models https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Method 2: Using PowerShell
Invoke-WebRequest -Uri "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf" -OutFile "llama_models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# Method 3: Manual download
# Visit: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF
# Download: mistral-7b-instruct-v0.2.Q4_K_M.gguf (4.37 GB)
# Place in: llama_models/
```

**Model Variants** (adjust based on VRAM):
- `Q4_K_M.gguf`: 4.37 GB - Recommended (good quality, moderate size)
- `Q5_K_M.gguf`: 5.13 GB - Better quality, requires more VRAM
- `Q3_K_M.gguf`: 3.52 GB - Lower quality, fits in limited VRAM

## Quick Start

### 1. Build and Start Services

```powershell
# Build DirectML service
docker compose -f docker-compose.yml -f docker-compose.directml.yml build llama-directml

# Start all services with DirectML backend
docker compose -f docker-compose.yml -f docker-compose.directml.yml up -d

# Watch logs to verify CLBlast initialization
docker compose -f docker-compose.directml.yml logs -f llama-directml
```

**Look for these log messages**:
```
BLAS = 1                                    ✅ CLBlast enabled
llm_load_tensors: using OpenCL for GPU     ✅ OpenCL backend active
ggml_opencl: selecting platform: 'AMD'     ✅ AMD GPU detected
```

**Warning signs** (GPU not working):
```
BLAS = 0                                    ❌ No GPU acceleration
llm_load_tensors: CPU buffer size = ...     ❌ CPU-only mode
```

### 2. Test the Service

```powershell
# Health check
Invoke-WebRequest -Uri "http://localhost:8082/health" | Select-Object -ExpandProperty Content

# Simple completion test
$body = @{
    prompt = "Explain DirectML in 3 bullet points:"
    max_tokens = 150
    temperature = 0.7
} | ConvertTo-Json

Invoke-WebRequest -Method POST -Uri "http://localhost:8082/v1/completions" `
    -ContentType "application/json" -Body $body | Select-Object -ExpandProperty Content | ConvertFrom-Json
```

Expected response time:
- **With GPU**: 3-7 seconds for 150 tokens
- **Without GPU**: 30-60+ seconds

### 3. Full Pipeline Test

```powershell
# Ingest test data
docker compose -f docker-compose.yml -f docker-compose.directml.yml run --rm `
    -v "$PWD/tests/fixtures/mailbox_sample:/app/tests/fixtures/mailbox_sample:ro" `
    ingestion python /app/upload_ingestion_sources.py /app/tests/fixtures/mailbox_sample/ingestion-config.json

docker compose -f docker-compose.yml -f docker-compose.directml.yml run --rm `
    -v "$PWD/tests/fixtures/mailbox_sample:/app/tests/fixtures/mailbox_sample:ro" `
    ingestion

# Verify summarization (should use GPU-accelerated LLM)
docker compose -f docker-compose.directml.yml logs -f summarization
```

## Performance Tuning

### GPU Layer Offloading

Adjust `LLAMA_GPU_LAYERS` in `docker-compose.directml.yml` based on VRAM:

| VRAM | Recommended Layers | Expected Performance |
|------|-------------------|----------------------|
| 8GB+ | 35 (full offload) | 40-70 tok/s |
| 6GB | 28-32 | 30-50 tok/s |
| 4GB | 20-24 | 20-35 tok/s |
| 2GB | 10-15 | 10-20 tok/s |

**How to adjust**:
```yaml
# In docker-compose.directml.yml
environment:
  - LLAMA_GPU_LAYERS=24  # Reduce if OOM errors occur
```

### Context Size

Reduce context window if you hit VRAM limits:

```yaml
environment:
  - LLAMA_CTX_SIZE=2048  # Default: 4096
```

### CPU Threads

Adjust threads for better CPU-GPU balance:

```yaml
environment:
  - LLAMA_THREADS=8  # Default: 4, increase for more CPU cores
```

## Troubleshooting

### Issue: `/dev/dxg` not found

**Symptoms**: Docker container fails to start with "no such device" error

**Solution**:
```powershell
# 1. Update WSL
wsl --update

# 2. Restart WSL
wsl --shutdown

# 3. Verify GPU drivers on Windows (AMD Adrenalin / Intel Graphics)

# 4. Check WSL kernel version (must be 5.10.102.1+)
wsl -e uname -r
```

### Issue: `BLAS = 0` in logs (CPU-only mode)

**Symptoms**: Slow inference, logs show "BLAS = 0" or "CPU buffer size"

**Possible causes**:
1. **CLBlast not compiled**: Rebuild image with `--no-cache`
   ```powershell
   docker compose -f docker-compose.directml.yml build --no-cache llama-directml
   ```

2. **OpenCL runtime missing**: Check container logs for OpenCL errors
   ```powershell
   docker compose -f docker-compose.directml.yml run --rm llama-directml clinfo
   ```

3. **GPU layers set to 0**: Verify `LLAMA_GPU_LAYERS` in docker-compose.directml.yml

### Issue: Out of Memory (OOM) errors

**Symptoms**: Container crashes or model fails to load

**Solution**:
```yaml
# Reduce GPU layers in docker-compose.directml.yml
environment:
  - LLAMA_GPU_LAYERS=20  # Start lower and increase gradually
  - LLAMA_CTX_SIZE=2048  # Reduce context size
```

### Issue: Slow performance despite GPU

**Symptoms**: GPU is detected but token generation is slow (< 10 tok/s)

**Checklist**:
1. **Verify GPU layers**: Check logs for "offloading X layers to GPU"
2. **Check VRAM usage**: Use `amd-smi` or Task Manager → Performance → GPU
3. **Model quantization**: Ensure using Q4_K_M or Q5_K_M (not FP16/FP32)
4. **PCIe bandwidth**: Ensure GPU is in PCIe x16 slot (not x4/x8)

### Issue: Cannot connect to service

**Symptoms**: `curl http://localhost:8082/health` fails

**Solution**:
```powershell
# Check if service is running
docker compose -f docker-compose.directml.yml ps

# Check logs
docker compose -f docker-compose.directml.yml logs llama-directml

# Verify port mapping
docker compose -f docker-compose.directml.yml port llama-directml 8082
```

## API Reference

### Health Check

```bash
GET http://localhost:8082/health
```

**Response**:
```json
{
  "status": "healthy",
  "model": "/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
  "gpu_layers": 35,
  "context_size": 4096
}
```

### OpenAI-Compatible Completion

```bash
POST http://localhost:8082/v1/completions
Content-Type: application/json

{
  "prompt": "Explain machine learning in simple terms:",
  "max_tokens": 150,
  "temperature": 0.7,
  "stop": ["</s>", "\n\n"]
}
```

**Response**:
```json
{
  "id": "cmpl-1234567890",
  "object": "text_completion",
  "created": 1234567890,
  "model": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
  "choices": [{
    "text": "Machine learning is...",
    "index": 0,
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 8,
    "completion_tokens": 42,
    "total_tokens": 50
  }
}
```

### Chat Completion

```bash
POST http://localhost:8082/v1/chat/completions
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What is DirectML?"}
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
```

### llama.cpp-Compatible Completion

```bash
POST http://localhost:8082/completion
Content-Type: application/json

{
  "prompt": "Once upon a time",
  "n_predict": 100,
  "temperature": 0.8,
  "stop": ["</s>"]
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Windows Host                                               │
│  ├─ AMD/Intel GPU Drivers (Adrenalin/Intel Graphics)       │
│  └─ DirectX 12 Runtime                                      │
└────────────────────┬────────────────────────────────────────┘
                     │ /dev/dxg passthrough
┌────────────────────▼────────────────────────────────────────┐
│  WSL2 (Ubuntu)                                              │
│  └─ Docker Container (llama-directml)                       │
│     ├─ OpenCL Runtime                                       │
│     ├─ CLBlast (GPU BLAS via OpenCL)                        │
│     ├─ llama-cpp-python (CLBlast-enabled)                   │
│     └─ Flask REST API (port 8082)                           │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP API
┌────────────────────▼────────────────────────────────────────┐
│  Summarization Service                                      │
│  └─ Uses LlamaCppSummarizer with DirectML backend          │
└─────────────────────────────────────────────────────────────┘
```

## Comparison with Other Backends

| Backend | Windows | AMD GPU | Setup | Performance | Stability |
|---------|---------|---------|-------|-------------|-----------|
| **DirectML** | ✅ Native | ✅ Excellent | ⭐⭐ Medium | ⭐⭐⭐⭐ Good | ⭐⭐⭐⭐ Good |
| **Ollama** | ✅ Native | ⚠️ Limited | ⭐ Easy | ⭐⭐ Poor (AMD) | ⭐⭐⭐⭐⭐ Excellent |
| **Vulkan** | ⚠️ Complex | ✅ Good | ⭐⭐⭐ Hard | ⭐⭐⭐⭐ Good | ⭐⭐⭐ Fair |
| **ROCm** | ❌ Linux only | ✅ Excellent | ⭐⭐⭐ Hard | ⭐⭐⭐⭐⭐ Best | ⭐⭐⭐⭐ Good |

**Recommendation**:
- **AMD GPU on Windows**: DirectML (this implementation)
- **NVIDIA GPU on Windows**: Ollama with CUDA
- **AMD GPU on Linux**: ROCm
- **Testing/Development**: Mock backend (CPU-only)

## Contributing

Issues and improvements for DirectML support:
- Report issues: [GitHub Issues](https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues)
- Performance benchmarks: Share your GPU model and tok/s in discussions
- Model compatibility: Test with other GGUF models

## References

- [DirectML Documentation](https://learn.microsoft.com/en-us/windows/ai/directml/dml)
- [llama.cpp CLBlast Support](https://github.com/ggerganov/llama.cpp#clblast)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [WSL2 GPU Compute](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute)
- [Docker Desktop WSL2](https://docs.docker.com/desktop/wsl/)

## License

SPDX-License-Identifier: MIT

Copyright (c) 2025 Copilot-for-Consensus contributors
