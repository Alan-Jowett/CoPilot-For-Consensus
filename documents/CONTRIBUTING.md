<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Contributing to Copilot-for-Consensus

Thank you for your interest in contributing! This project thrives on community collaboration and follows open-source best practices for transparency, inclusivity, and quality.

***

## Project Governance

See [GOVERNANCE.md](./GOVERNANCE.md) for details.

***

## How to Contribute

### Reporting Issues

*   Use the **Issues** tab for:
    *   Bug reports
    *   Feature requests
    *   Documentation improvements
*   Include clear details, steps to reproduce, and expected behavior.

### Submitting Pull Requests

*   Fork the repository and create a feature branch:

    ```sh
    git checkout -b feature/my-new-feature
    ```
*   Follow coding standards:
    *   Python: PEP 8 compliance
    *   Include docstrings and type hints
*   Add tests for new functionality.
*   Submit a PR with:
    *   A descriptive title
    *   Clear explanation of changes
    *   Reference related issues (if any)

### Code of Conduct

*   All contributors must adhere to the [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).
*   Be respectful, inclusive, and constructive in all interactions.

***

## Development Guidelines

*   **Architecture:** Microservice-based, containerized design.
*   **Language:** Python-first for accessibility.
*   **Testing:** Unit tests for core logic, integration tests for pipeline components.
*   **Documentation:** Update README.md and relevant docs for any new feature.

***

## Idempotency Requirements

All processing stages in the pipeline **must be idempotent** to support safe retries and message redelivery. This ensures system resilience and prevents data corruption or duplicate side effects.

### What is Idempotency?

An operation is idempotent if performing it multiple times with the same input produces the same result as performing it once, without unintended side effects.

### Why Idempotency Matters

*   **Message Queue Retries:** RabbitMQ may redeliver messages on failures or restarts.
*   **Service Restarts:** Services requeue unacknowledged messages on startup.
*   **Network Failures:** Transient errors can cause duplicate processing attempts.
*   **Data Integrity:** Prevents duplicate records, redundant API calls, or inconsistent state.

### Idempotency Patterns

#### 1. Database Operations

**Use Unique Constraints and Handle Duplicates:**

```python
from pymongo.errors import DuplicateKeyError

try:
    document_store.insert_document("messages", message)
except DuplicateKeyError:
    # Already exists - skip gracefully (idempotent retry)
    logger.debug(f"Message {message['message_id']} already exists, skipping")
```

**Use Upsert Semantics:**

```python
# Vector stores should use upsert (create or update)
vector_store.add_embeddings(ids, vectors, metadatas)  # Safe to call multiple times
```

#### 2. State Checks Before Side Effects

**Check for Existing Results:**

```python
# Check if summary already exists before regenerating
existing = document_store.query_documents(
    collection="summaries",
    filter_dict={"thread_id": thread_id, "summary_type": "thread"},
    limit=1
)
if existing:
    logger.info(f"Summary exists for {thread_id}, skipping (idempotent retry)")
    return
```

#### 3. Event Publishing

**Design Events to be Replayable:**

*   Include deterministic IDs derived from input data (e.g., SHA256 hashes).
*   Events should carry all necessary context to be processed independently.
*   Downstream consumers should also be idempotent.

#### 4. Status Updates

**Make Status Transitions Safe:**

```python
# Only update if not already in target state
document_store.update_document(
    collection="chunks",
    doc_id=chunk_id,
    patch={"embedding_generated": True},
)
# Safe to call multiple times - no harm if already True
```

### Testing for Idempotency

**Always add tests that verify duplicate message delivery:**

```python
def test_idempotent_processing(service, mock_store):
    """Verify service handles duplicate messages gracefully."""
    event_data = {"message_id": "test-123", ...}
    
    # Process once
    service.process(event_data)
    assert mock_store.insert.call_count == 1
    
    # Process again (simulating retry)
    service.process(event_data)
    # Should not insert duplicate or fail
    assert mock_store.insert.call_count == 1  # Still 1 (duplicate skipped)
```

### Service-Specific Guidelines

*   **Parsing:** Uses `message_key` (deterministic hash) as primary key. DuplicateKeyError is caught and logged.
*   **Chunking:** Uses `chunk_id` (SHA256 hash). Duplicate chunks are skipped gracefully.
*   **Embedding:** Vectorstore uses upsert semantics. Chunk status updates are safe to retry.
*   **Summarization:** Checks for existing summaries before LLM calls to avoid redundant generation.
*   **Orchestration:** Checks for existing summaries before publishing SummarizationRequested events.

***

## Review Process

*   PRs reviewed by at least two maintainers.
*   Automated checks (linting, tests) must pass before merging.
*   Significant changes may require design discussions via GitHub Discussions.

***

## Long-Term Vision

Contributors are encouraged to think beyond MVP:

*   Interactive subject matter expert powered by RFCs and mailing list history.
*   Semantic search and Q&A capabilities.
*   Multi-language support and accessibility features.

***

## Licensing

By contributing, you agree that your contributions will be licensed under the MIT License.

***

## Join the Community

*   Participate in GitHub Discussions.
*   Share ideas and feedback.
*   Help us build an open, transparent, and impactful tool for technical collaboration.

***

**Thank you for helping make Copilot-for-Consensus better!**

***
