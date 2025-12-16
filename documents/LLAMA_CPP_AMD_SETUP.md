# AMD GPU Support with llama.cpp

This guide explains how to enable AMD GPU acceleration for local LLM inference using llama.cpp with Vulkan, OpenCL, or ROCm backends.

## Overview

The CoPilot-For-Consensus project supports AMD GPU acceleration through **llama.cpp**, which provides better AMD GPU support than Ollama, especially for:
- **Integrated GPUs** (APUs like AMD Radeon 780M, 680M)
- **Windows users** with AMD GPUs
- **Discrete AMD GPUs** on Linux

## Why llama.cpp for AMD?

| Feature | llama.cpp | Ollama |
|---------|-----------|--------|
| **Integrated GPU support** | ✅ Excellent (Vulkan) | ⚠️ Limited |
| **Windows AMD GPU** | ✅ Works well (Vulkan) | ❌ Poor support |
| **Discrete AMD GPU (Linux)** | ✅ Good (ROCm/Vulkan) | ✅ Good (ROCm) |
| **Cross-platform** | ✅ Vulkan works everywhere | ⚠️ Linux-focused |
| **Special toolkit required** | ❌ No (just GPU drivers) | ⚠️ ROCm on Linux |
| **Quantized models** | ✅ Efficient GGUF | ✅ Supported |

## AMD GPU Backend Options

### Vulkan Backend (Recommended for Most Users)

**Best for:**
- Integrated GPUs (AMD Radeon 780M, 680M, etc.)
- Windows users with any AMD GPU
- Users who want simple setup without ROCm

**Requirements:**
- AMD GPU with Vulkan support (any modern AMD GPU/APU)
- Updated AMD drivers (Adrenalin for Windows, Mesa/AMDGPU for Linux)
- Docker with device access configured

**Platforms:** Windows, Linux

### OpenCL Backend

**Best for:**
- Older AMD GPUs without good Vulkan support
- Legacy systems

**Requirements:**
- AMD GPU with OpenCL support
- AMD drivers with OpenCL runtime

**Platforms:** Windows, Linux

### ROCm Backend

**Best for:**
- Discrete AMD GPUs (RX 6000/7000 series)
- Linux servers requiring maximum performance

**Requirements:**
- Discrete AMD GPU (RX 6000/7000 series recommended)
- ROCm drivers installed
- Linux kernel 5.x+
- Docker with ROCm support

**Platforms:** Linux only

## Quick Start: Using llama.cpp with AMD GPU

### 1. Enable llama.cpp service

Edit your `docker-compose.yml` or create a `docker-compose.override.yml`:

```yaml
services:
  llama-cpp:
    profiles: []  # Remove profile to enable by default
    devices:
      - /dev/dri:/dev/dri  # Enable AMD GPU access (Vulkan/OpenCL)
```

For **ROCm** backend (discrete AMD GPUs on Linux):

```yaml
services:
  llama-cpp:
    profiles: []
    deploy:
      resources:
        reservations:
          devices:
            - driver: amdgpu
              capabilities: [gpu]
```

### 2. Configure summarization service

Set environment variables to use llama.cpp:

**Linux/macOS (bash):**
```bash
# In .env file or export
export LLM_BACKEND=llamacpp
export LLM_MODEL=mistral-7b-instruct-v0.2.Q4_K_M
export LLAMACPP_HOST=http://llama-cpp:8081
```

**Windows (PowerShell):**
```powershell
# Set environment variables
$env:LLM_BACKEND = "llamacpp"
$env:LLM_MODEL = "mistral-7b-instruct-v0.2.Q4_K_M"
$env:LLAMACPP_HOST = "http://llama-cpp:8081"
```

Or in `docker-compose.override.yml`:

```yaml
services:
  summarization:
    environment:
      - LLM_BACKEND=llamacpp
      - LLM_MODEL=mistral-7b-instruct-v0.2.Q4_K_M
      - LLAMACPP_HOST=http://llama-cpp:8081
```

### 3. Download a GGUF model

The llama.cpp service uses a Docker named volume (`llama_models`) for model storage. You have two options:

**Option A: Use a bind mount (recommended for easier management)**

Create a `docker-compose.override.yml` to replace the named volume with a local directory:

```yaml
services:
  llama-cpp:
    volumes:
      - ./llama_models:/models  # Bind mount to local directory
```

Then download models to the local directory:

**Linux/macOS:**
```bash
# Create models directory
mkdir -p llama_models

# Download a model (example: Mistral 7B Q4_K_M)
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -O llama_models/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Or using curl
curl -L https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -o llama_models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

**Windows (PowerShell):**
```powershell
# Create models directory
New-Item -ItemType Directory -Path "llama_models" -Force

# Download a model using Invoke-WebRequest
Invoke-WebRequest -Uri "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf" `
  -OutFile "llama_models\mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

**Option B: Use the named volume (default)**

If you keep the default named volume, download models into the container:

```bash
# Start a temporary container with the volume mounted
docker run --rm -v llama_models:/models -v $(pwd):/download alpine sh -c \
  "wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
   -O /models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# Or copy a local file into the volume
docker cp mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  $(docker create -v llama_models:/models alpine):/models/
```

### 4. Configure model path

Set the model path in environment variables:

**Linux/macOS (bash):**
```bash
export LLAMA_MODEL=/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

**Windows (PowerShell):**
```powershell
$env:LLAMA_MODEL = "/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

### 5. Start the services

```bash
docker compose up -d llama-cpp summarization
```

## Model Selection Guide

Choose a model based on your VRAM constraints:

### For AMD Radeon 780M (Integrated GPU)

The 780M has access to shared system memory but benefits from smaller, quantized models:

| Model | Size | VRAM Usage | Speed | Quality | Recommended |
|-------|------|------------|-------|---------|-------------|
| **Mistral 7B Q4_K_M** | 4.1 GB | ~5 GB | Fast | Good | ✅ Best balance |
| Llama 2 7B Q4_K_M | 4.1 GB | ~5 GB | Fast | Good | ✅ Good |
| Mistral 7B Q5_K_M | 5.0 GB | ~6 GB | Medium | Better | ⚠️ If 8GB+ RAM |
| Phi-2 Q8_0 | 3.0 GB | ~4 GB | Very Fast | Good | ✅ Budget option |
| Mistral 7B Q8_0 | 7.7 GB | ~9 GB | Slower | Best | ❌ Only if 16GB+ RAM |

### For Discrete AMD GPUs (RX 6000/7000)

With dedicated VRAM, you can use larger models:

| VRAM | Recommended Models |
|------|-------------------|
| **4-6 GB** | Mistral 7B Q4_K_M, Llama 2 7B Q4_K_M |
| **8 GB** | Mistral 7B Q5_K_M, Llama 2 7B Q5_K_M |
| **12-16 GB** | Mistral 7B Q8_0, Llama 2 13B Q4_K_M |
| **24 GB+** | Llama 2 13B Q8_0, CodeLlama 34B Q4_K_M |

### Quantization Levels Explained

- **Q4_K_M**: 4-bit quantization, medium quality, **best balance** for most users
- **Q5_K_M**: 5-bit quantization, better quality, slightly larger
- **Q8_0**: 8-bit quantization, near-original quality, 2x larger
- **Q2_K**: 2-bit quantization, smallest, lower quality (not recommended)

## Performance Tuning

### Adjust GPU Layers

The `LLAMA_GPU_LAYERS` controls how many model layers are offloaded to GPU:

```bash
# Default (good for 6-8GB VRAM)
export LLAMA_GPU_LAYERS=35

# For integrated GPUs with limited memory
export LLAMA_GPU_LAYERS=20

# For discrete GPUs with lots of VRAM
export LLAMA_GPU_LAYERS=50
```

**Tips:**
- Start with 35 and adjust based on performance
- Lower value = less VRAM usage, slower inference
- Higher value = more VRAM usage, faster inference
- Set to 0 to disable GPU (CPU-only fallback)

### Adjust Context Size

Control memory usage with context window size:

```bash
# Default (balanced)
export LLAMA_CTX_SIZE=4096

# For lower memory usage
export LLAMA_CTX_SIZE=2048

# For larger contexts (if VRAM allows)
export LLAMA_CTX_SIZE=8192
```

## Platform-Specific Setup

### Windows

1. **Install AMD Adrenalin drivers** (latest version)
   - Download from: https://www.amd.com/en/support

2. **Enable WSL2 GPU support** (for Docker Desktop)
   - Ensure Docker Desktop is using WSL2 backend
   - GPU passthrough should work automatically

3. **Configure docker-compose.yml**:
   ```yaml
   llama-cpp:
     profiles: []
     devices:
       - /dev/dri:/dev/dri  # WSL2 GPU passthrough
   ```

4. **Start services**:
   ```powershell
   docker compose up -d llama-cpp summarization
   ```

### Linux

1. **Install AMD drivers**
   ```bash
   # Ubuntu/Debian (Mesa/AMDGPU)
   sudo apt update
   sudo apt install mesa-vulkan-drivers vulkan-tools
   
   # For ROCm (discrete GPUs)
   # Follow: https://rocm.docs.amd.com/en/latest/deploy/linux/quick_start.html
   ```

2. **Verify Vulkan support**
   ```bash
   vulkaninfo | grep deviceName
   ```

3. **Add user to render/video groups** (for device access)
   ```bash
   sudo usermod -a -G render,video $USER
   # Log out and back in for changes to take effect
   ```

4. **Configure docker-compose.yml**:
   ```yaml
   llama-cpp:
     profiles: []
     devices:
       - /dev/dri:/dev/dri
   ```

5. **Start services**:
   ```bash
   docker compose up -d llama-cpp summarization
   ```

## Troubleshooting

### GPU not detected

**Check Vulkan support:**
```bash
# On Linux
vulkaninfo | grep deviceName

# In Docker container
docker compose run --rm llama-cpp vulkaninfo
```

**Check device access:**
```bash
ls -la /dev/dri/
# Should show renderD128 or similar
```

**Fix permissions (Linux):**
```bash
sudo usermod -a -G render,video $USER
# Log out and back in
```

### Out of memory errors

**Reduce GPU layers:**
```bash
export LLAMA_GPU_LAYERS=20
```

**Use smaller quantization:**
```bash
# Switch from Q5_K_M to Q4_K_M
export LLAMA_MODEL=/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

**Reduce context size:**
```bash
export LLAMA_CTX_SIZE=2048
```

### Slow inference

**Increase GPU layers:**
```bash
export LLAMA_GPU_LAYERS=40
```

**Check GPU is being used:**
```bash
# Monitor GPU usage (Linux)
watch -n 1 radeontop

# Or check logs
docker compose logs llama-cpp | grep -i gpu
```

**Verify Vulkan backend is active:**
```bash
docker compose logs llama-cpp | grep -i vulkan
```

### Model loading fails

**Check model path:**
```bash
docker compose exec llama-cpp ls -la /models/
```

**Verify GGUF format:**
```bash
file llama_models/your-model.gguf
# Should show: data
```

**Check model compatibility:**
- Ensure model is in GGUF format (not GGML or other formats)
- Download from trusted sources (HuggingFace, TheBloke)

## Finding GGUF Models

### Recommended Sources

1. **HuggingFace** (primary source)
   - Search for "GGUF": https://huggingface.co/models?search=gguf
   - TheBloke's quantized models: https://huggingface.co/TheBloke

2. **Popular Models**
   - Mistral 7B Instruct: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF
   - Llama 2 7B: https://huggingface.co/TheBloke/Llama-2-7B-GGUF
   - Phi-2: https://huggingface.co/TheBloke/phi-2-GGUF
   - CodeLlama: https://huggingface.co/TheBloke/CodeLlama-7B-GGUF

### Download Models

```bash
# Using wget
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -O llama_models/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Using curl
curl -L https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  -o llama_models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

## Switching Between Ollama and llama.cpp

You can easily switch between Ollama (for NVIDIA GPUs) and llama.cpp (for AMD GPUs):

**Use Ollama (NVIDIA GPU):**
```bash
export LLM_BACKEND=local
export LLM_MODEL=mistral
export OLLAMA_HOST=http://ollama:11434
```

**Use llama.cpp (AMD GPU):**
```bash
export LLM_BACKEND=llamacpp
export LLM_MODEL=mistral-7b-instruct-v0.2.Q4_K_M
export LLAMACPP_HOST=http://llama-cpp:8081
```

## Performance Benchmarks

### AMD Radeon 780M (Integrated GPU)

| Model | Tokens/sec | Latency (first token) | VRAM Usage |
|-------|------------|----------------------|------------|
| Mistral 7B Q4_K_M | ~15-20 | ~2s | 5 GB |
| Llama 2 7B Q4_K_M | ~15-18 | ~2s | 5 GB |
| Phi-2 Q8_0 | ~25-30 | ~1s | 4 GB |

### AMD RX 6700 XT (12GB Discrete GPU)

| Model | Tokens/sec | Latency (first token) | VRAM Usage |
|-------|------------|----------------------|------------|
| Mistral 7B Q4_K_M | ~40-50 | ~1s | 5 GB |
| Mistral 7B Q8_0 | ~25-35 | ~1.5s | 9 GB |
| Llama 2 13B Q4_K_M | ~20-25 | ~2s | 8 GB |

*Benchmarks are approximate and depend on system configuration*

## Resources

- **llama.cpp GitHub**: https://github.com/ggerganov/llama.cpp
- **llama.cpp server docs**: https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md
- **GGUF models (HuggingFace)**: https://huggingface.co/models?search=gguf
- **AMD ROCm documentation**: https://rocm.docs.amd.com/
- **Vulkan documentation**: https://www.vulkan.org/

## Next Steps

- See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines
- See [README.md](../README.md) for general project documentation
- Report issues at: https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues
