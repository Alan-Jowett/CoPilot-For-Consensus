<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# DirectML-Enabled llama.cpp Server

This directory contains the DirectML-enabled llama.cpp server for AMD/Intel GPU acceleration on Windows/WSL2.

## Files

- **Dockerfile**: Builds the DirectML-enabled llama.cpp image with CLBlast support
- **server.py**: Flask REST API server with OpenAI-compatible endpoints

## How It Works

1. **OpenCL Runtime**: Provides GPU access via `/dev/dxg` device (WSL2 DirectML)
2. **CLBlast**: GPU-accelerated BLAS library using OpenCL
3. **llama-cpp-python**: Built with CLBlast support (`CMAKE_ARGS="-DLLAMA_CLBLAST=on"`)
4. **Flask API**: Exposes OpenAI-compatible endpoints for LLM inference

## Endpoints

- `GET /health` - Health check
- `POST /v1/completions` - OpenAI-compatible text completion
- `POST /v1/chat/completions` - OpenAI-compatible chat completion
- `POST /completion` - llama.cpp-compatible completion (for backward compatibility)
- `GET /metrics` - Prometheus metrics

## Environment Variables

- `LLAMA_MODEL`: Path to GGUF model file (default: `/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf`)
- `LLAMA_GPU_LAYERS`: Number of layers to offload to GPU (default: `35` for Mistral 7B)
- `LLAMA_CTX_SIZE`: Context window size in tokens (default: `4096`)
- `LLAMA_THREADS`: CPU threads for non-GPU operations (default: `4`)
- `LLAMA_VERBOSE`: Enable verbose logging to verify GPU usage (default: `true`)

## Build

```bash
docker build -t copilot-llama-directml:latest .
```

## Run Standalone

```bash
docker run -it --rm \
  -v ./models:/models:ro \
  --device /dev/dxg:/dev/dxg \
  -e LLAMA_MODEL=/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -e LLAMA_GPU_LAYERS=35 \
  -p 8082:8082 \
  copilot-llama-directml:latest
```

## Verify GPU Acceleration

Look for these log messages on startup:

```
BLAS = 1                                    ✅ CLBlast enabled
llm_load_tensors: using OpenCL for GPU     ✅ GPU backend active
ggml_opencl: selecting platform: 'AMD'     ✅ AMD GPU detected
llm_load_tensors: offloading 35 layers     ✅ Layers offloaded to GPU
```

## Performance

Expected token generation speed (Mistral 7B Q4_K_M):

| Hardware | GPU Layers | Speed |
|----------|-----------|-------|
| AMD RX 7900 XT | 35 | 50-70 tok/s |
| AMD RX 6800 | 35 | 40-60 tok/s |
| AMD Radeon 780M | 35 | 15-25 tok/s |
| Intel Arc A770 | 35 | 20-40 tok/s |
| CPU only (0 layers) | 0 | 5-10 tok/s |

## Troubleshooting

### `BLAS = 0` (No GPU Acceleration)

**Cause**: llama-cpp-python not built with CLBlast support

**Solution**: Rebuild with `--no-cache`:
```bash
docker build --no-cache -t copilot-llama-directml:latest .
```

### Out of Memory

**Cause**: Too many layers offloaded to GPU for available VRAM

**Solution**: Reduce `LLAMA_GPU_LAYERS`:
```bash
# For 4GB VRAM
-e LLAMA_GPU_LAYERS=20

# For 2GB VRAM
-e LLAMA_GPU_LAYERS=10
```

### `/dev/dxg` not found

**Cause**: WSL2 GPU support not enabled or GPU drivers not installed

**Solution**: See [DIRECTML_SETUP.md](../DIRECTML_SETUP.md#prerequisites)

## Integration

This service integrates with the summarization service via the `llamacpp` backend.

See [docker-compose.directml.yml](../docker-compose.directml.yml) for the full configuration.

## License

SPDX-License-Identifier: MIT

Copyright (c) 2025 Copilot-for-Consensus contributors
