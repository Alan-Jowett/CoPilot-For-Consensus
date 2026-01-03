<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Summarization Service

## Overview

The Summarization Service turns retrieved context into concise, citation-rich summaries and insights. It consumes orchestration requests, pulls the top-k chunks from the vector store plus metadata from the document DB, and calls the configured LLM backend (local or cloud) to generate thread-level or weekly rollups. Outputs include inline citations back to source messages and draft mentions for traceability.

## Purpose

- Generate thread and weekly summaries after orchestration triggers
- Provide consensus/dissent signals with inline citations
- Track draft mentions and action items per thread
- Emit completion events so reporting and dashboards stay fresh

## Responsibilities

- **Event-driven summarization:** React to `SummarizationRequested` events
- **Context assembly:** Fetch top-k chunks + metadata for each thread
- **Prompting:** Apply system/user templates and guardrails for style, safety, and citations
- **LLM execution:** Call local (Ollama) or cloud (Azure/OpenAI) backends
- **Output packaging:** Produce Markdown/JSON with citations and metrics (tokens, latency)
- **Publishing:** Emit `SummaryComplete` or `SummarizationFailed` events

## Technology Stack

- **Language:** Python 3.10+
- **Orchestration:** Event-driven via message bus
- **Retrieval:** Qdrant (vector) + MongoDB (metadata)
- **LLM Backends:** Ollama (local), Azure OpenAI, OpenAI API
- **Observability:** Prometheus metrics + structured JSON logs

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MESSAGE_BUS_HOST` | String | Yes | `messagebus` | Message bus hostname |
| `MESSAGE_BUS_PORT` | Integer | No | `5672` | Message bus port |
| `MESSAGE_BUS_USER` | String | No | `guest` | Message bus username |
| `MESSAGE_BUS_PASSWORD` | String | No | `guest` | Message bus password |
| `DOCUMENT_DATABASE_HOST` | String | Yes | `documentdb` | Document DB host |
| `DOCUMENT_DATABASE_PORT` | Integer | No | `27017` | Document DB port |
| `DOCUMENT_DATABASE_NAME` | String | No | `copilot` | Database name |
| `VECTOR_DB_HOST` | String | Yes | `vectorstore` | Vector store host |
| `VECTOR_DB_PORT` | Integer | No | `6333` | Vector store port (Qdrant) |
| `VECTOR_DB_COLLECTION` | String | No | `message_embeddings` | Vector collection name |
| `LLM_BACKEND` | String | No | `ollama` | `ollama`, `azure`, or `openai` |
| `LLM_MODEL` | String | No | `mistral` | Model to use for summaries |
| `LLM_TEMPERATURE` | Float | No | `0.2` | Sampling temperature |
| `LLM_MAX_TOKENS` | Integer | No | `2048` | Max tokens for outputs |
| `CONTEXT_WINDOW_TOKENS` | Integer | No | `3000` | Token budget for retrieved context |
| `TOP_K` | Integer | No | `12` | Chunks to retrieve per thread |
| `CITATION_COUNT` | Integer | No | `12` | Maximum citations per summary |
| `CITATION_TEXT_MAX_LENGTH` | Integer | No | `300` | Maximum length for citation text snippets (characters) |
| `LLM_TIMEOUT_SECONDS` | Integer | No | `300` | LLM request timeout in seconds (5 min for CPU inference) |
| `RETRY_MAX_ATTEMPTS` | Integer | No | `3` | Retry attempts on failures |
| `RETRY_BACKOFF_SECONDS` | Integer | No | `5` | Base backoff interval |
| `AZURE_OPENAI_KEY` | String | No | - | Azure OpenAI API key (if using Azure) |
| `AZURE_OPENAI_ENDPOINT` | String | No | - | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | String | No | `gpt-35-turbo` | Azure deployment name |
| `OPENAI_API_KEY` | String | No | - | OpenAI API key (if using OpenAI) |
| `OLLAMA_HOST` | String | No | `http://ollama:11434` | Ollama server URL |
| `SYSTEM_PROMPT_PATH` | String | No | `/app/prompts/system.txt` | System prompt file |
| `USER_PROMPT_PATH` | String | No | `/app/prompts/user.txt` | User prompt template |
| `LOG_LEVEL` | String | No | `INFO` | Logging level |

### Backend Examples

**Local (Ollama):**
```bash
LLM_BACKEND=ollama
LLM_MODEL=mistral
OLLAMA_HOST=http://ollama:11434
# For CPU inference, increase timeout to allow sufficient generation time
LLM_TIMEOUT_SECONDS=300  # 5 minutes (default)
# Reduce prompt size to fit within context limits
CITATION_TEXT_MAX_LENGTH=300  # characters (default)
```

**Note on CPU Performance:** When running Ollama on CPU without GPU acceleration, LLM inference is significantly slower. The default timeout of 300 seconds (5 minutes) is calibrated for CPU inference with models like Mistral-7B. If you experience timeouts:
- Increase `LLM_TIMEOUT_SECONDS` (e.g., 600 for 10 minutes)
- Reduce `TOP_K` to use fewer context chunks (e.g., 8 instead of 12)
- Consider using a smaller/faster model (e.g., TinyLlama, Phi-2)
- For production workloads, enable GPU acceleration:
  - NVIDIA GPUs with Ollama: See [OLLAMA_GPU_SETUP.md](../documents/OLLAMA_GPU_SETUP.md)
  - AMD GPUs with llama.cpp: See [LLAMA_CPP_AMD_SETUP.md](../documents/LLAMA_CPP_AMD_SETUP.md)

**Azure OpenAI:**
```bash
LLM_BACKEND=azure
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-35-turbo
```

**OpenAI API:**
```bash
LLM_BACKEND=openai
OPENAI_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
```

## Events

### Subscribes To

The Summarization Service subscribes to the following events. See [SCHEMA.md](../docs/schemas/data-storage.md#message-bus-event-schemas) for complete event schemas.

1) **SummarizationRequested**
   - **Exchange:** `copilot.events`
   - **Routing Key:** `summarization.requested`
   - See [SummarizationRequested schema](../docs/schemas/data-storage.md#9-summarizationrequested) in SCHEMA.md
   - **Behavior:** For each thread, retrieve context, build prompt, call LLM, produce summary with citations.

### Publishes

The Summarization Service publishes the following events. See [SCHEMA.md](../docs/schemas/data-storage.md#message-bus-event-schemas) for complete event schemas.

1) **SummaryComplete**
   - **Exchange:** `copilot.events`
   - **Routing Key:** `summary.complete`
   - See [SummaryComplete schema](../docs/schemas/data-storage.md#11-summarycomplete) in SCHEMA.md
   - **Behavior:** Contains the completed summary with markdown formatting, citations, and LLM performance metrics.

2) **SummarizationFailed**
   - **Exchange:** `copilot.events`
   - **Routing Key:** `summarization.failed`
   - See [SummarizationFailed schema](../docs/schemas/data-storage.md#12-summarizationfailed) in SCHEMA.md
   - **Behavior:** Signals summarization errors for specific threads with error details and retry information.

## Data Flow

```mermaid
graph LR
    A[SummarizationRequested Event] --> B[Summarization Service]
    B --> C[Vector Store (Qdrant)]
    B --> D[Document DB (MongoDB)]
    C --> B
    D --> B
    B --> E{LLM Backend}
    E -->|Local| F[Ollama]
    E -->|Azure| G[Azure OpenAI]
    E -->|OpenAI| H[OpenAI API]
    F --> I[Summary Draft]
    G --> I
    H --> I
    I --> J[SummaryComplete Event]
    J --> K[Reporting / Dashboard]
```

## Summarization Flow (Pseudo-code)

```python
def handle_summarization_requested(event):
    for thread_id in event.data.thread_ids:
        context = retrieve_context(thread_id, top_k=cfg.top_k)
        prompt = build_prompt(context, cfg.system_prompt, cfg.user_prompt)
        result = call_llm(prompt, backend=cfg.llm_backend, model=cfg.llm_model)
        summary = format_with_citations(result, context, max_citations=cfg.citation_count)
        publish_summary_complete(thread_id, summary, result.metrics)
```

## API Endpoints

- `GET /health` — service health and config snapshot
- `POST /summaries` — generate summary for provided `thread_ids` (manual trigger)
- `GET /stats` — counts of processed events, average latency, backend usage

## Error Handling

- Retries with exponential backoff for transient failures
- Dead-letter queue for irrecoverable events
- Timeouts and circuit breakers around vector store and LLM calls
- Input validation on routing keys and payload schemas

## Monitoring & Metrics

Prometheus metrics exposed at `/metrics`:
- `summarization_events_total` (labeled by event_type, outcome)
- `summarization_latency_seconds` (histogram: end-to-end per thread)
- `summarization_llm_calls_total` (labeled by backend/model)
- `summarization_failures_total` (labeled by error_type)
- `summarization_tokens_total` (prompt vs completion)

Structured logs (JSON) include thread_id, backend, model, tokens, citations, and latency.

## Dependencies

- **Message Bus:** RabbitMQ or Azure Service Bus
- **Vector Store:** Qdrant (default) via `VECTOR_DB_HOST`
- **Document DB:** MongoDB for message metadata and chunk lookups
- **LLM Backend:** Ollama or Azure/OpenAI depending on `LLM_BACKEND`

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export MESSAGE_BUS_HOST=localhost
export VECTOR_DB_HOST=localhost
export DOCUMENT_DATABASE_HOST=localhost
python main.py

# Docker
docker build -t copilot-summarization .
docker run -d \
  -e MESSAGE_BUS_HOST=messagebus \
  -e VECTOR_DB_HOST=vectorstore \
  -e DOCUMENT_DATABASE_HOST=documentdb \
  -e LLM_BACKEND=ollama \
  copilot-summarization
```

## Future Enhancements

- [ ] Streaming summaries with incremental citations
- [ ] Quality estimation and self-evaluation prompts
- [ ] Style profiles (concise, detailed, executive) per consumer
- [ ] Multi-thread batch summarization with deduplication
- [ ] Token-cost accounting and rate-limit adaptation
- [ ] Automated regression suite for summary quality
