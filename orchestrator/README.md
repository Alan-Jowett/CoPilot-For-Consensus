<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Orchestration Service

## Overview

The Orchestration Service coordinates retrieval, prompt assembly, and summarization workflows across the pipeline. It listens for new embeddings, gathers the most relevant context from the vector store and document database, and triggers summarization jobs using the configured LLM backend (local or cloud). Built on Semantic Kernel, it keeps summarization deterministic, auditable, and vendor-agnostic.

## Purpose

- Coordinate end-to-end summarization after new content is embedded
- Retrieve top-k chunks per thread and assemble prompt context
- Invoke LLMs with flexible backend selection (local or cloud)
- Track consensus/dissent, draft mentions, and citations
- Publish downstream events so reporting and dashboards stay current

## Responsibilities

- **Event-driven orchestration:** React to `EmbeddingsGenerated` events
- **Context retrieval:** Query vector store + doc DB for thread context
- **Prompt building:** Insert system/user prompts, guardrails, and citations
- **LLM invocation:** Route to local (Ollama) or cloud (Azure/OpenAI) backends
- **Summarization trigger:** Kick off summarization jobs per thread or batch window
- **Quality controls:** Enforce token budgets, content filters, retry/backoff
- **Progress tracking:** Emit events for success/failure and timings

## Technology Stack

- **Language:** Python 3.11+
- **Framework:** Semantic Kernel (Python SDK)
- **Message Bus:** RabbitMQ (default) or Azure Service Bus
- **Retrieval:** Qdrant (vector) + MongoDB (metadata)
- **LLM Backends:** Ollama (local), Azure OpenAI, OpenAI API
- **Observability:** Prometheus + structured JSON logs

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MESSAGE_BUS_HOST` | String | Yes | `messagebus` | Message bus hostname |
| `MESSAGE_BUS_PORT` | Integer | No | `5672` | Message bus port |
| `MESSAGE_BUS_USER` | String | No | `guest` | Message bus username |
| `MESSAGE_BUS_PASSWORD` | String | No | `guest` | Message bus password |
| `DOC_DB_HOST` | String | Yes | `documentdb` | Document DB host |
| `DOC_DB_PORT` | Integer | No | `27017` | Document DB port |
| `DOC_DB_NAME` | String | No | `copilot` | Database name |
| `VECTOR_DB_HOST` | String | Yes | `vectorstore` | Vector store host |
| `VECTOR_DB_PORT` | Integer | No | `6333` | Vector store port (Qdrant) |
| `VECTOR_DB_COLLECTION` | String | No | `message_embeddings` | Vector collection |
| `LLM_BACKEND` | String | No | `ollama` | `ollama`, `azure`, or `openai` |
| `LLM_MODEL` | String | No | `mistral` | Model name/identifier |
| `LLM_TEMPERATURE` | Float | No | `0.2` | Sampling temperature |
| `LLM_MAX_TOKENS` | Integer | No | `2048` | Max tokens for responses |
| `TOP_K` | Integer | No | `12` | Retrieval top-k per thread |
| `CONTEXT_WINDOW_TOKENS` | Integer | No | `3000` | Budget for prompt context |
| `BATCH_INTERVAL_SECONDS` | Integer | No | `300` | Time-window batching for summaries |
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
```

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

The Orchestration Service subscribes to the following events. See [SCHEMA.md](../documents/SCHEMA.md#message-bus-event-schemas) for complete event schemas.

1) **EmbeddingsGenerated**  
   - **Exchange:** `copilot.events`  
   - **Routing Key:** `embeddings.generated`  
   - See [EmbeddingsGenerated schema](../documents/SCHEMA.md#7-embeddingsgenerated) in SCHEMA.md
   - **Behavior:** Fetch chunk metadata; compute thread scope; retrieve top-k from vector store; assemble prompt; trigger summarization job.

2) **JSONParsed** *(optional for thread bookkeeping)*  
   - **Exchange:** `copilot.events`  
   - **Routing Key:** `json.parsed`
   - See [JSONParsed schema](../documents/SCHEMA.md#3-jsonparsed) in SCHEMA.md
   - **Behavior:** Track new threads/messages; maintain orchestration schedule.

### Publishes

The Orchestration Service publishes the following events. See [SCHEMA.md](../documents/SCHEMA.md#message-bus-event-schemas) for complete event schemas.

1) **SummarizationRequested**  
   - **Exchange:** `copilot.events`  
   - **Routing Key:** `summarization.requested`  
   - See [SummarizationRequested schema](../documents/SCHEMA.md#9-summarizationrequested) in SCHEMA.md
   - **Behavior:** Triggers summarization with LLM configuration and context parameters.

2) **SummaryComplete** *(relayed)*  
   - **Exchange:** `copilot.events`  
   - **Routing Key:** `summary.complete`  
   - See [SummaryComplete schema](../documents/SCHEMA.md#11-summarycomplete) in SCHEMA.md
   - **Behavior:** Forward summary results or acknowledge completion to downstream services.

3) **OrchestrationFailed**  
   - **Exchange:** `copilot.events`  
   - **Routing Key:** `orchestration.failed`  
   - See [OrchestrationFailed schema](../documents/SCHEMA.md#10-orchestrationfailed) in SCHEMA.md
   - **Behavior:** Signals orchestration errors for specific threads.

## Data Flow

```mermaid
graph LR
    A[EmbeddingsGenerated Event] --> B[Orchestration Service]
    B --> C[Vector Store (Qdrant)]
    B --> D[Document DB (MongoDB)]
    C --> B
    D --> B
    B --> E{LLM Backend}
    E -->|Local| F[Ollama]
    E -->|Azure| G[Azure OpenAI]
    E -->|OpenAI| H[OpenAI API]
    F --> I[Draft Summary]
    G --> I
    H --> I
    I --> J[SummarizationRequested Event]
    J --> K[Summarization Service]
    K --> L[SummaryComplete Event]
    L --> M[Reporting / Dashboard]
```

## Orchestration Flow (Pseudo-code)

```python
def handle_embeddings_generated(event):
    thread_ids = resolve_threads(event.data.chunk_ids)
    for thread_id in thread_ids:
        context = retrieve_context(thread_id, top_k=cfg.top_k)
        prompt = build_prompt(context, cfg.system_prompt, cfg.user_prompt)
        result = call_llm(prompt, backend=cfg.llm_backend, model=cfg.llm_model)
        publish_summarization_requested(thread_id, prompt, cfg)
        log_metrics(thread_id, context, result)
```

## API Endpoints

- `GET /health` — service health and config snapshot
- `POST /orchestrate` — trigger orchestration for a thread list (payload: `{ "thread_ids": [...] }`)
- `GET /stats` — counts of processed events, average latency, backend usage

## Error Handling

- Retries with exponential backoff for message processing failures
- Dead-letter queue for irrecoverable events
- Timeouts and circuit breakers around vector store and LLM calls
- Input validation on routing keys and payload schemas

## Monitoring & Metrics

Prometheus metrics exposed at `/metrics`:
- `orchestration_events_total` (labeled by event_type, outcome)
- `orchestration_latency_seconds` (histogram: end-to-end per thread)
- `orchestration_llm_calls_total` (labeled by backend/model)
- `orchestration_failures_total` (labeled by error_type)

Structured logs (JSON) include thread_id, backend, model, token counts, and latency.

## Dependencies

- **Message Bus:** RabbitMQ or Azure Service Bus
- **Vector Store:** Qdrant (default) reachable via `VECTOR_DB_HOST`
- **Document DB:** MongoDB for message metadata
- **LLM Backend:** Ollama server or Azure/OpenAI APIs depending on `LLM_BACKEND`

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export MESSAGE_BUS_HOST=localhost
export VECTOR_DB_HOST=localhost
export DOC_DB_HOST=localhost
python main.py

# Docker
docker build -t copilot-orchestrator .
docker run -d \
  -e MESSAGE_BUS_HOST=messagebus \
  -e VECTOR_DB_HOST=vectorstore \
  -e DOC_DB_HOST=documentdb \
  -e LLM_BACKEND=ollama \
  copilot-orchestrator
```

## Future Enhancements

- [ ] Planner-based skill chaining with Semantic Kernel
- [ ] Streaming summarization responses
- [ ] Per-tenant prompt templates and guardrails
- [ ] Token-cost accounting and rate-limit adaptation
- [ ] Canary/backfill modes for historical threads
