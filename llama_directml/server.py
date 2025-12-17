# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""DirectML-enabled llama.cpp server with OpenAI-compatible API.

This server provides GPU-accelerated LLM inference using DirectML (via CLBlast)
for AMD/Intel GPUs on Windows/WSL2. It exposes OpenAI-compatible endpoints
for seamless integration with existing LLM applications.
"""

import os
import sys
import time
import logging
from typing import Optional
from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import llama-cpp-python
try:
    from llama_cpp import Llama
except ImportError as e:
    logger.error("Failed to import llama_cpp: %s", e)
    logger.error("Make sure llama-cpp-python is installed with CLBlast support")
    sys.exit(1)

# Initialize Flask app
app = Flask(__name__)

# Prometheus metrics
completion_counter = Counter(
    'llama_directml_completions_total',
    'Total number of completions',
    ['status']
)
completion_latency = Histogram(
    'llama_directml_completion_latency_seconds',
    'Completion latency in seconds'
)
tokens_generated = Counter(
    'llama_directml_tokens_generated_total',
    'Total number of tokens generated'
)

# Configuration from environment variables
# Note: Model path must be configured via LLAMA_MODEL environment variable
# Default is an example path - the model file must be downloaded separately (see DIRECTML_SETUP.md)
MODEL_PATH = os.getenv("LLAMA_MODEL", "/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")
GPU_LAYERS = int(os.getenv("LLAMA_GPU_LAYERS", "35"))
CTX_SIZE = int(os.getenv("LLAMA_CTX_SIZE", "4096"))
THREADS = int(os.getenv("LLAMA_THREADS", "4"))
VERBOSE = os.getenv("LLAMA_VERBOSE", "true").lower() == "true"

# Global LLM instance
llm: Optional[Llama] = None


def initialize_llm():
    """Initialize the LLM model with GPU acceleration."""
    global llm
    
    logger.info("Initializing LLM with configuration:")
    logger.info("  Model: %s", MODEL_PATH)
    logger.info("  GPU Layers: %d", GPU_LAYERS)
    logger.info("  Context Size: %d", CTX_SIZE)
    logger.info("  Threads: %d", THREADS)
    
    if not os.path.exists(MODEL_PATH):
        logger.error("Model file not found: %s", MODEL_PATH)
        logger.error("Please ensure the model is mounted at /models/")
        sys.exit(1)
    
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=GPU_LAYERS,  # Offload layers to GPU
            n_ctx=CTX_SIZE,           # Context window size
            n_threads=THREADS,        # CPU threads for non-GPU ops
            verbose=VERBOSE,          # Enable verbose logging to see CLBlast usage
        )
        logger.info("LLM initialized successfully")
        logger.info("Check logs above for 'BLAS = 1' or 'CLBlast' to verify GPU acceleration")
    except Exception as e:
        logger.error("Failed to initialize LLM: %s", e)
        sys.exit(1)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint.
    
    Returns 200 OK even during initialization to prevent container restarts.
    Check 'status' field to determine if service is ready.
    """
    if llm is None:
        return jsonify({
            "status": "initializing",
            "message": "LLM is still loading",
            "ready": False
        }), 200
    
    return jsonify({
        "status": "healthy",
        "ready": True,
        "model": MODEL_PATH,
        "gpu_layers": GPU_LAYERS,
        "context_size": CTX_SIZE
    }), 200


@app.route("/v1/completions", methods=["POST"])
def v1_completions():
    """OpenAI-compatible /v1/completions endpoint."""
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 503
    
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        max_tokens = data.get("max_tokens", 512)
        temperature = data.get("temperature", 0.7)
        stop = data.get("stop", ["</s>"])
        
        logger.info("Received completion request (prompt_length=%d)", len(prompt))
        
        start_time = time.time()
        
        # Generate completion
        response = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
            echo=False
        )
        
        latency = time.time() - start_time
        
        # Extract response
        text = response["choices"][0]["text"]
        prompt_tokens = response["usage"]["prompt_tokens"]
        completion_tokens = response["usage"]["completion_tokens"]
        
        # Update metrics
        completion_counter.labels(status="success").inc()
        completion_latency.observe(latency)
        tokens_generated.inc(completion_tokens)
        
        logger.info(
            "Completion successful (tokens: %d+%d, latency: %.2fs, speed: %.1f tok/s)",
            prompt_tokens, completion_tokens, latency,
            completion_tokens / latency if latency > 0 else 0
        )
        
        # Return OpenAI-compatible response
        return jsonify({
            "id": f"cmpl-{int(time.time())}",
            "object": "text_completion",
            "created": int(time.time()),
            "model": os.path.basename(MODEL_PATH),
            "choices": [{
                "text": text,
                "index": 0,
                "logprobs": None,
                "finish_reason": response["choices"][0]["finish_reason"]
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }), 200
        
    except Exception as e:
        logger.error("Completion failed: %s", e, exc_info=True)
        completion_counter.labels(status="error").inc()
        return jsonify({"error": str(e)}), 500


@app.route("/v1/chat/completions", methods=["POST"])
def v1_chat_completions():
    """OpenAI-compatible /v1/chat/completions endpoint."""
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 503
    
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens", 512)
        temperature = data.get("temperature", 0.7)
        stop = data.get("stop", ["</s>"])
        
        # Convert chat messages to prompt using Mistral instruction format
        # Format: <s>[INST] {user_message} [/INST]{assistant_message}</s>
        # Note: This template is specific to Mistral models. Other models require different templates.
        prompt_parts = []
        last_role = None
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Validate role alternation for proper formatting
            if role == "user" and last_role == "user":
                logger.warning("Consecutive user messages detected - combining into single message")
            
            if role == "system":
                # System messages treated as initial instruction
                prompt_parts.append(f"<s>[INST] {content} [/INST]")
            elif role == "user":
                if prompt_parts and last_role == "assistant":
                    # New turn after assistant response
                    prompt_parts.append(f"<s>[INST] {content} [/INST]")
                elif prompt_parts:
                    # Continue existing instruction
                    prompt_parts.append(f"[INST] {content} [/INST]")
                else:
                    # First message
                    prompt_parts.append(f"<s>[INST] {content} [/INST]")
            elif role == "assistant":
                prompt_parts.append(f"{content}</s>")
            
            last_role = role
        
        prompt = "".join(prompt_parts)
        
        logger.info("Received chat completion request (%d messages)", len(messages))
        
        start_time = time.time()
        
        # Generate completion
        response = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
            echo=False
        )
        
        latency = time.time() - start_time
        
        # Extract response
        text = response["choices"][0]["text"]
        prompt_tokens = response["usage"]["prompt_tokens"]
        completion_tokens = response["usage"]["completion_tokens"]
        
        # Update metrics
        completion_counter.labels(status="success").inc()
        completion_latency.observe(latency)
        tokens_generated.inc(completion_tokens)
        
        logger.info(
            "Chat completion successful (tokens: %d+%d, latency: %.2fs, speed: %.1f tok/s)",
            prompt_tokens, completion_tokens, latency,
            completion_tokens / latency if latency > 0 else 0
        )
        
        # Return OpenAI-compatible response
        return jsonify({
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": os.path.basename(MODEL_PATH),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": response["choices"][0]["finish_reason"]
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }), 200
        
    except Exception as e:
        logger.error("Chat completion failed: %s", e, exc_info=True)
        completion_counter.labels(status="error").inc()
        return jsonify({"error": str(e)}), 500


@app.route("/completion", methods=["POST"])
def completion():
    """llama.cpp-compatible /completion endpoint."""
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 503
    
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        n_predict = data.get("n_predict", 512)
        temperature = data.get("temperature", 0.7)
        stop = data.get("stop", ["</s>"])
        
        logger.info("Received completion request (llama.cpp format)")
        
        start_time = time.time()
        
        # Generate completion
        response = llm(
            prompt,
            max_tokens=n_predict,
            temperature=temperature,
            stop=stop,
            echo=False
        )
        
        latency = time.time() - start_time
        
        # Extract response
        text = response["choices"][0]["text"]
        completion_tokens = response["usage"]["completion_tokens"]
        
        # Update metrics
        completion_counter.labels(status="success").inc()
        completion_latency.observe(latency)
        tokens_generated.inc(completion_tokens)
        
        logger.info(
            "Completion successful (latency: %.2fs, speed: %.1f tok/s)",
            latency, completion_tokens / latency if latency > 0 else 0
        )
        
        # Return llama.cpp-compatible response
        return jsonify({
            "content": text,
            "stop": True,
            "generation_settings": {
                "n_predict": n_predict,
                "temperature": temperature
            }
        }), 200
        
    except Exception as e:
        logger.error("Completion failed: %s", e, exc_info=True)
        completion_counter.labels(status="error").inc()
        return jsonify({"error": str(e)}), 500


@app.route("/metrics", methods=["GET"])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    logger.info("Starting DirectML-enabled llama.cpp server")
    
    # Initialize LLM on startup
    initialize_llm()
    
    # Start Flask server
    logger.info("Starting Flask server on port 8082")
    app.run(host="0.0.0.0", port=8082, threaded=True)
