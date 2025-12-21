<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Schema Registry

This document lists all registered schemas in the Copilot-for-Consensus system.

**Total schemas:** 21

## Event Schemas

| Type | Version | Path |
|------|---------|------|
| ArchiveIngested | v1 | `events/ArchiveIngested.schema.json` |
| ArchiveIngestionFailed | v1 | `events/ArchiveIngestionFailed.schema.json` |
| ChunkingFailed | v1 | `events/ChunkingFailed.schema.json` |
| ChunksPrepared | v1 | `events/ChunksPrepared.schema.json` |
| EmbeddingGenerationFailed | v1 | `events/EmbeddingGenerationFailed.schema.json` |
| EmbeddingsGenerated | v1 | `events/EmbeddingsGenerated.schema.json` |
| EventEnvelope | v1 | `events/event-envelope.schema.json` |
| JSONParsed | v1 | `events/JSONParsed.schema.json` |
| OrchestrationFailed | v1 | `events/OrchestrationFailed.schema.json` |
| ParsingFailed | v1 | `events/ParsingFailed.schema.json` |
| ReportDeliveryFailed | v1 | `events/ReportDeliveryFailed.schema.json` |
| ReportPublished | v1 | `events/ReportPublished.schema.json` |
| SummarizationFailed | v1 | `events/SummarizationFailed.schema.json` |
| SummarizationRequested | v1 | `events/SummarizationRequested.schema.json` |
| SummaryComplete | v1 | `events/SummaryComplete.schema.json` |

## Document Schemas

| Type | Version | Path |
|------|---------|------|
| Archive | v1 | `documents/archives.schema.json` |
| Chunk | v1 | `documents/chunks.schema.json` |
| Message | v1 | `documents/messages.schema.json` |
| Summary | v1 | `documents/summaries.schema.json` |
| Thread | v1 | `documents/threads.schema.json` |

## Role Store Schemas

| Type | Version | Path |
|------|---------|------|
| UserRoles | v1 | `role_store/user_roles.schema.json` |

## Usage Examples

```python
from copilot_schema_validation import load_schema, get_schema_path

# Load a schema
schema = load_schema("ArchiveIngested", "v1")

# Get the path to a schema file
path = get_schema_path("Archive", "v1")
```

