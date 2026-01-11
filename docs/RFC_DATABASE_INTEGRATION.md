<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# RFC Database Integration: Feature Design Document

**Status**: Draft
**Author**: Copilot-for-Consensus Team
**Date**: 2025-12-28
**Version**: 1.0

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background and Motivation](#background-and-motivation)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Architecture Overview](#architecture-overview)
5. [Ingestion Strategy](#ingestion-strategy)
6. [Semantic Chunking and Embedding](#semantic-chunking-and-embedding)
7. [Cross-Linking with Mailing List Threads](#cross-linking-with-mailing-list-threads)
8. [Prompt Augmentation](#prompt-augmentation)
9. [UI/UX Considerations](#uiux-considerations)
10. [Data Models and Schemas](#data-models-and-schemas)
11. [API Design](#api-design)
12. [Implementation Phases](#implementation-phases)
13. [Performance and Scalability](#performance-and-scalability)
14. [Security and Compliance](#security-and-compliance)
15. [Testing Strategy](#testing-strategy)
16. [Operational Considerations](#operational-considerations)
17. [Open Questions](#open-questions)
18. [References](#references)

---

## Executive Summary

This feature design document proposes integrating the IETF RFC corpus into Copilot-for-Consensus to enable semantic linking, contextual grounding, and traceable consensus modeling. By incorporating the canonical source of IETF standards, the system will better contextualize mailing list discussions, trace normative references, and provide richer, citation-grounded summaries and Q&A capabilities.

**Key Deliverables:**
- RFC ingestion service with version tracking
- Section-aware semantic chunking and embedding
- Cross-linking between mailing list threads and RFC sections
- Enhanced prompt augmentation with RFC context
- RFC browser UI with semantic search and visualization
- Comprehensive API for RFC querying and citation

**Expected Impact:**
- Bridge the gap between deliberation (mailing lists) and specification (RFCs)
- Enable better contextual understanding of technical discussions
- Support traceable consensus modeling with normative references
- Enhance support for chairs, editors, and working group participants


## Background and Motivation

### Current State

Copilot-for-Consensus currently focuses on:
- Ingesting and parsing mailing list archives
- Summarizing thread discussions
- Tracking draft mentions and evolution
- Providing semantic search over email content

### The Gap

The system lacks direct access to the RFC corpus—the ultimate product of the IETF consensus process. This creates several limitations:

1. **Limited Context**: Summaries cannot ground discussions in the normative text they reference
2. **Missing Links**: No direct connection between "RFC 9000 specifies..." in emails and actual RFC 9000 content
3. **Incomplete Understanding**: Cannot answer questions like "What does RFC 9000 say about connection migration?"
4. **Traceability Gap**: Cannot trace how consensus discussions map to final specifications

### Why This Matters

Integrating RFCs enables:
- **Contextual Grounding**: Summaries can include relevant RFC excerpts and definitions
- **Semantic Linking**: Automatic connection between discussions and specification text
- **Enhanced Q&A**: Direct queries over RFC content ("What are the security considerations in RFC 9000?")
- **Consensus Tracing**: Map discussion topics to normative requirements (MUST/SHOULD/MAY)
- **Citation Validation**: Verify that discussions accurately reference specification content
- **Draft Evolution**: Track how drafts evolve into RFCs over time

---

## Goals and Non-Goals

### Goals

1. **RFC Corpus Access**: Ingest and maintain the complete IETF RFC corpus
2. **Semantic Search**: Enable semantic search over RFC content with section-level granularity
3. **Cross-Linking**: Automatically link mailing list discussions to relevant RFC sections
4. **Prompt Enhancement**: Inject RFC context into summarization and Q&A prompts
5. **Normative Tagging**: Detect and tag RFC requirements (MUST/SHOULD/MAY per RFC 2119)
6. **Version Tracking**: Track RFC versions, obsolescence, and updates
7. **User Interface**: Provide intuitive RFC browsing and search capabilities
8. **API Integration**: Expose RFC data via REST API for programmatic access

### Non-Goals (for Initial Release)

1. **Full RFC Diffing**: Complete diff engine between RFC versions (future enhancement)
2. **Real-time RFC Tracking**: Live monitoring of RFC publication (batch updates sufficient)
3. **Non-IETF Standards**: Integration with W3C, IEEE, or other standards bodies
4. **RFC Authoring**: Tools for creating or editing RFCs
5. **Performance Optimization**: Sub-second latency for RFC queries (acceptable: <5s)
6. **Multi-Language Support**: Non-English RFC translations


## Architecture Overview

### System Context

The RFC integration adds new services while integrating with existing architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                     RFC Integration Layer                    │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ RFC Ingestion│  RFC Parser  │ RFC Chunking │ RFC Embedding  │
│   Service    │   Service    │   Service    │    Service     │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │                │
       ▼              ▼              ▼                ▼
┌────────────────────────────────────────────────────────────┐
│                    Storage Layer                            │
├──────────────────────────┬─────────────────────────────────┤
│   RFC Document Store     │    RFC Vector Store             │
│      (MongoDB)           │      (Qdrant)                   │
└──────────────────────────┴─────────────────────────────────┘
                │                        │
                ▼                        ▼
┌────────────────────────────────────────────────────────────┐
│                Existing Services Enhanced                   │
├────────────┬───────────────┬───────────────┬───────────────┤
│  Parsing   │ Orchestrator  │Summarization  │   Web UI      │
│  Service   │   Service     │   Service     │   (React)     │
└────────────┴───────────────┴───────────────┴───────────────┘
```

### Design Principles

1. **Reuse Existing Patterns**: Follow established microservice, event-driven architecture
2. **Loose Coupling**: RFC services integrate via message bus and REST APIs
3. **Incremental Rollout**: RFC features can be enabled/disabled independently
4. **Backward Compatibility**: Existing services continue to work without RFC integration
5. **Performance Isolation**: RFC processing doesn't block mailing list pipeline

---

## Ingestion Strategy

### RFC Data Sources

#### Primary Source: RFC Editor (rfc-editor.org)

**Advantages:**
- Official, authoritative source
- XML2RFC format with semantic structure
- Includes metadata (authors, dates, obsolescence info)
- Stable URLs and versioning

**Access Methods:**
1. **Bulk Download**: rsync from `rsync://ftp.rfc-editor.org/rfcs-text-only`
2. **Individual Fetch**: HTTPS download `https://www.rfc-editor.org/rfc/rfc{number}.xml`
3. **Datatracker API**: Metadata from `https://datatracker.ietf.org/api/v1/doc/document/`

#### Secondary Source: IETF Datatracker

**Advantages:**
- Rich metadata (working groups, status, relationships)
- Draft-to-RFC mapping
- Submission history and author information

**API Endpoints:**
- Document List: `/api/v1/doc/document/?rfc={number}`
- Relationships: `/api/v1/doc/relateddocument/?relationship=replaces&target=rfc{number}`

### Ingestion Architecture

#### RFC Ingestion Service

New microservice: `rfc-ingestion`

**Responsibilities:**
- Fetch RFCs from RFC Editor and Datatracker
- Detect new/updated RFCs
- Publish `RFCIngested` events
- Track ingestion state and checksums
- Handle rate limiting and retries

**Configuration Example:**
```json
{
  "service_name": "rfc-ingestion",
  "fields": {
    "rfc_source_url": {
      "type": "string",
      "default": "https://www.rfc-editor.org/rfc/",
      "description": "Base URL for RFC downloads"
    },
    "ingestion_mode": {
      "type": "string",
      "default": "incremental",
      "enum": ["full", "incremental"]
    },
    "ingestion_schedule": {
      "type": "string",
      "default": "0 2 * * *",
      "description": "Cron expression for periodic sync (evaluated in UTC)"
    }
  }
}
```

**Event Published: `RFCIngested`**
```json
{
  "event_type": "RFCIngested",
  "timestamp": "2025-12-28T10:00:00Z",
  "rfc_number": 9000,
  "file_path": "/data/rfcs/rfc9000.xml",
  "format": "xml",
  "checksum": "sha256:abc123...",
  "metadata": {
    "title": "QUIC: A UDP-Based Multiplexed...",
    "authors": ["J. Iyengar", "M. Thomson"],
    "date": "2021-05"
  }
}
```

### RFC Parser Service

New microservice: `rfc-parser`

**Responsibilities:**
- Parse XML2RFC format into structured JSON
- Extract metadata (title, authors, date, status)
- Identify sections, subsections, figures, and references
- Normalize text formatting
- Detect normative language (MUST/SHOULD/MAY)
- Store parsed RFCs in document database

**Event Subscribed: `RFCIngested`**

**Event Published: `RFCParsed`**
```json
{
  "event_type": "RFCParsed",
  "timestamp": "2025-12-28T10:05:00Z",
  "rfc_number": 9000,
  "section_count": 23,
  "section_ids": ["abstract", "1", "1.1", "1.2", ...],
  "normative_count": {
    "MUST": 45,
    "SHOULD": 23,
    "MAY": 12
  }
}
```

**Note on `section_ids` ordering**: The `section_ids` array is ordered in depth-first traversal order (e.g., "1", "1.1", "1.1.1", "1.2", "2", "2.1", etc.) to ensure consistent processing by downstream services (chunking, navigation).

### Storage Strategy

#### Document Store (MongoDB)

**Collection: `rfcs`**
```json
{
  "_id": "rfc9000",
  "rfc_number": 9000,
  "title": "QUIC: A UDP-Based Multiplexed and Secure Transport",
  "authors": ["J. Iyengar", "M. Thomson"],
  "date": "2021-05",
  "status": "PROPOSED STANDARD",
  "sections": [
    {
      "section_id": "1",
      "title": "Introduction",
      "content": "...",
      "subsections": ["1.1", "1.2"]
    }
  ],
  "normative_requirements": [
    {
      "section_id": "7.2",
      "requirement_type": "MUST",
      "text": "Clients MUST discard..."
    }
  ],
  "normative_metadata_source": "derived_from_rfc_document"
}
```

---

## Semantic Chunking and Embedding

### RFC Chunking Strategy

#### Section-Aware Chunking

RFCs have well-defined structure. Leverage this for semantic chunks:

**Chunking Rules:**
1. **Abstract**: Single chunk (typically <500 tokens)
2. **Sections**: Each section = base chunk
3. **Large Sections**: Split at subsection boundaries
4. **Overflow**: If section >1000 tokens, split with overlap
5. **Preserve Context**: Include section path (e.g., "RFC 9000 § 7.2.1")

**Example Chunk:**
```json
{
  "chunk_id": "rfc9000-section-7.2",
  "rfc_number": 9000,
  "section_id": "7.2",
  "section_title": "Negotiating Connection IDs",
  "section_path": "7. Cryptographic Handshake > 7.2",
  "content": "The connection ID is a variable-length...",
  "token_count": 487,
  "normative_language": ["MUST", "SHOULD"]
}
```

### Embedding Generation

#### RFC Embedding Service

New microservice: `rfc_embedding` (or extend existing `embedding` service)

**Responsibilities:**
- Generate embeddings for RFC chunks
- Use same embedding model as mailing list content (consistency)
- Store embeddings in vector database
- Support hybrid search (semantic + keyword)

**Vector Store Strategy:**

**Qdrant Collection: `rfc_chunks`**
```json
{
  "id": "rfc9000-section-7.2",
  "vector": [0.123, -0.456, ...],
  "payload": {
    "rfc_number": 9000,
    "section_id": "7.2",
    "section_title": "Negotiating Connection IDs",
    "content": "The connection ID is...",
    "normative_language": ["MUST", "SHOULD"]
  }
}
```

### Normative Language Detection

#### RFC 2119 Keywords

Detect and tag normative language per RFC 2119:
- **MUST**: Absolute requirement
- **SHOULD**: Recommendation
- **MAY**: Optional

**Detection Pattern:**
```python
import re

from typing import List

NORMATIVE_PATTERN = re.compile(
    r'\b(MUST(?:\s+NOT)?|SHOULD(?:\s+NOT)?|MAY|REQUIRED)\b'
)

def detect_normative_language(text: str) -> List[str]:
    return list({match.group(0) for match in NORMATIVE_PATTERN.finditer(text)})
```

---

## Cross-Linking with Mailing List Threads

### RFC Reference Detection

#### Detection Strategy

**Pattern Matching:**
Extend existing draft detection in `parsing` service:

```python
RFC_REFERENCE_PATTERN = re.compile(
    r'\bRFC[-\s]?(\d{4,5})\b',
    re.IGNORECASE
)

SECTION_REFERENCE_PATTERN = re.compile(
    r'(?:RFC[-\s]?(\d{4,5}))?[§\s]*[Ss]ection\s+(\d+(?:\.\d+)*)',
    re.IGNORECASE
)
```

**Examples Matched:**
- "RFC 9000"
- "RFC9000" (without space)
- "RFC-9000" (with hyphen)
- "RFC 9000 Section 7.2"
- "Section 7.2 of RFC 9000"

**Note on Section Reference Pattern**: The pattern handles optional RFC numbers, but for complete coverage, consider splitting into separate patterns for "RFC X Section Y", "Section Y of RFC X", and standalone "Section Y" references to ensure all cases are captured correctly.

**Enhanced Message Schema:**
```json
{
  "message_id": "msg-12345",
  "body": "...",
  "rfc_references": [
    {
      "rfc_number": 9000,
      "section_id": "7.2",
      "mention_context": "...discusses RFC 9000 Section 7.2..."
    }
  ]
}
```

### Semantic Linking Service

New microservice: `rfc-linker`

**Responsibilities:**
- Subscribe to `MessageParsed` events
- Detect RFC references in message text
- Perform semantic search for best-matching RFC sections
- Store bidirectional links (message ↔ RFC section)

**Link Storage:**

**Collection: `rfc_message_links`**
```json
{
  "message_id": "msg-12345",
  "thread_id": "thread-789",
  "rfc_number": 9000,
  "section_id": "7.2",
  "link_type": "explicit",
  "confidence": 1.0,
  "mention_context": "We should follow RFC 9000 Section 7.2..."
}
```

**`link_type` values:**
- `explicit`: The message contains a direct textual citation of the RFC (and optionally section), e.g., "RFC 9000 Section 7.2"
- `semantic`: The RFC section is linked based on semantic similarity of the content, even if the RFC is not mentioned in the message
- `user_created`: A link manually added by a user through the UI or API

Implementations SHOULD treat `link_type` as an enumerated field with the values above and keep this list in sync across services.

---

## Prompt Augmentation

### Retrieval-Augmented Generation (RAG) with RFCs

#### Enhanced Orchestrator Service

Extend `orchestrator` service to include RFC context in prompts.

**Workflow:**
1. **Query Expansion**: Extract key terms from thread/message
2. **RFC Retrieval**: Query vector store for relevant RFC sections
3. **Context Ranking**: Rank RFC sections by relevance
4. **Prompt Injection**: Include top-k RFC sections in LLM prompt
5. **Citation Generation**: Ensure summaries cite RFC sources

**Example Prompt:**
```
You are summarizing a technical discussion about QUIC connection migration.

**Relevant RFC Context:**

RFC 9000 § 9: Connection Migration
> An endpoint can change the IP address or port...
> [MUST] Endpoints MUST validate new paths before migrating.

**Discussion Thread:**
[Message 1] Alice: "I think we need to clarify path validation..."
[Message 2] Bob: "RFC 9000 already covers this..."

**Task:** Summarize the key points and consensus, citing relevant RFC sections.
```

### Q&A Over RFCs

Enable direct Q&A over RFC content:

**Query Example:**
"What does RFC 9000 say about connection migration?"

**Q&A Workflow:**
1. Parse user question
2. Retrieve relevant RFC sections (vector search)
3. Generate answer with LLM + RAG
4. Include inline citations

---

## UI/UX Considerations

### RFC Browser

#### Main Features

1. **RFC List View**: Browse all RFCs with search and filters
2. **RFC Detail View**: View full RFC content with navigation
3. **Section Navigation**: Table of contents with jump-to-section
4. **Semantic Search**: Search across all RFCs semantically
5. **Citation View**: See mailing list references to RFC sections

#### Example UI Components

**RFC List Page:**
```
┌────────────────────────────────────────────────────┐
│ RFC Browser                        [Search: ____] │
├────────────────────────────────────────────────────┤
│ RFC 9000 - QUIC: A UDP-Based Multiplexed...       │
│ May 2021 | Proposed Standard | 151 pages          │
│ [View] [Cited 47 times in discussions]            │
└────────────────────────────────────────────────────┘
```

**RFC Detail Page:**
```
┌────────────────────────────────────────────────────┐
│ RFC 9000: QUIC Transport Protocol                  │
├─────────────┬──────────────────────────────────────┤
│ TOC         │ 7.2 Negotiating Connection IDs       │
│ Abstract    │ The connection ID is a variable-     │
│ 1. Intro    │ length field...                      │
│ 7. Crypto   │                                      │
│ ├ 7.2 ◄     │ **MUST**: Clients MUST discard...    │
└─────────────┴──────────────────────────────────────┘
```

### Semantic Search

**Search Features:**
- Auto-complete with RFC numbers and titles
- Filter by normative language (MUST/SHOULD/MAY)
- Sort by relevance or date
- Highlight matching text

---

## Data Models and Schemas

### Event Schemas

#### RFCIngested Event

```json
{
  "event_type": "RFCIngested",
  "version": "1.0",
  "timestamp": "2025-12-28T10:00:00Z",
  "rfc_number": 9000,
  "file_path": "/data/rfcs/rfc9000.xml",
  "metadata": {
    "title": "QUIC: A UDP-Based Multiplexed...",
    "authors": ["J. Iyengar", "M. Thomson"]
  }
}
```

#### RFCParsed Event

```json
{
  "event_type": "RFCParsed",
  "version": "1.0",
  "timestamp": "2025-12-28T10:05:00Z",
  "rfc_number": 9000,
  "section_count": 23,
  "normative_count": {
    "MUST": 45,
    "SHOULD": 23,
    "MAY": 12
  }
}
```

---

## API Design

### REST API Endpoints

**API Versioning**: All endpoints use the `/api/v1/` prefix to support future API evolution without breaking existing clients. This is especially important given the 6-phase rollout plan where API contracts may need to evolve.

#### RFC Retrieval

**GET /api/v1/rfcs**
- List all RFCs with pagination and filtering
- Query params: `status`, `year`, `wg`, `search`, `page`, `per_page`

**GET /api/v1/rfcs/{rfc_number}**
- Get complete RFC document with sections

**GET /api/v1/rfcs/{rfc_number}/sections/{section_id}**
- Get specific section content

#### RFC Search

**POST /api/v1/rfcs/search**
- Semantic search over RFC content
```json
{
  "query": "path validation requirements",
  "filters": {
    "status": ["PROPOSED STANDARD"],
    "normative_language": ["MUST"]
  },
  "limit": 10
}
```

#### RFC-Message Links

**GET /api/v1/rfcs/{rfc_number}/citations**
- Get all mailing list messages citing this RFC

**GET /api/v1/messages/{message_id}/rfc-links**
- Get all RFC sections linked to this message

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-4)

**Goals:**
- RFC ingestion and storage infrastructure
- Basic parsing and normalization

**Deliverables:**
1. RFC ingestion service
2. RFC parser service
3. Database schemas
4. Testing

**Success Criteria:**
- Successfully ingest and parse RFC 9000-9010
- All sections stored with correct hierarchy
- Events published to message bus

### Phase 2: Semantic Search (Weeks 5-8)

**Goals:**
- Enable semantic search over RFC content
- RFC chunking and embedding

**Deliverables:**
1. RFC chunking service
2. RFC embedding service
3. Search API
4. Testing

**Success Criteria:**
- Search query "connection migration" returns RFC 9000 § 9
- Top-5 results have >0.8 relevance

### Phase 3: Cross-Linking (Weeks 9-12)

**Goals:**
- Link mailing list discussions to RFCs
- Automatic RFC reference detection

**Deliverables:**
1. RFC linker service
2. Enhanced message parsing
3. Link API
4. Testing

**Success Criteria:**
- Messages mentioning "RFC 9000 Section 7" are linked
- Link detection accuracy >90%

### Phase 4: Prompt Augmentation (Weeks 13-16)

**Goals:**
- Enhance summaries with RFC context
- RFC-grounded Q&A

**Deliverables:**
1. Orchestrator enhancements
2. Q&A service
3. Summarization updates
4. Testing

**Success Criteria:**
- Summaries include relevant RFC excerpts
- Q&A answers cite specific sections

### Phase 5: UI & Visualization (Weeks 17-20)

**Goals:**
- User-facing RFC browser
- Citation graphs and analytics

**Deliverables:**
1. RFC browser UI
2. Search interface
3. Citation views
4. Visualizations

**Success Criteria:**
- Users can browse and search RFCs
- Citations are clickable and navigable

### Phase 6: Production Hardening (Weeks 21-24)

**Goals:**
- Performance optimization
- Monitoring and alerting
- Documentation

**Deliverables:**
1. Performance optimization
2. Observability
3. Documentation
4. Deployment

**Success Criteria:**
- RFC search <1s p95 latency
- 99.9% uptime
- Complete documentation

---

## Performance and Scalability

### Expected Load

**RFC Corpus Size:**
- Total RFCs: ~9500 (as of 2025)
- Average RFC size: ~50 pages (~100KB text)
- Total corpus: ~950MB text
- Embedded corpus: ~20GB (with vectors)

**Growth Rate:**
- New RFCs: ~300/year

### Performance Targets

| Operation | Target Latency (p95) | Target Throughput |
|-----------|---------------------|-------------------|
| RFC retrieval | <100ms | 100 req/s |
| Section retrieval | <50ms | 200 req/s |
| Semantic search | <5s | 20 req/s |
| Q&A workflow | <5s | 5 req/s |

**Note on Performance Targets**: These targets align with the stated non-goal of sub-second latency for RFC queries (line 103); for the initial release, p95 latencies under 5 seconds for semantic search and Q&A workflows are considered acceptable. The Phase 6 success criterion of "<1s p95 latency" (line 714) refers to optimized performance after production hardening, not the initial release baseline.

### Scalability Strategy

**Horizontal Scaling:**
- All services stateless (scale via replicas)
- Vector store: Qdrant cluster mode
- Document store: MongoDB replica set

**Caching:**
- Cache frequently accessed RFCs (top 100)
- Cache search results (5-minute TTL)

**Indexing:**
- MongoDB indexes on `rfc_number`, `section_id`, `status`
- Qdrant HNSW index for vectors

---

## Security and Compliance

### Data Sensitivity

**Public Data:**
- RFCs are public documents (no confidentiality concerns)
- Can be freely cached and distributed
- Attribution required per RFC Editor terms

### Access Control

**Authentication:**
- RFC browser: Public read access (no auth required)
- RFC search: Public access
- Manual link creation: Requires authentication
- Admin operations: Requires admin role

### Compliance

**Licensing:**
- RFCs distributed under IETF Trust Legal Provisions
- Attribution to RFC Editor required

**Rate Limiting:**
- RFC Editor: Respect robots.txt and rate limits
- Internal: No rate limits for authenticated users

---

## Testing Strategy

### Unit Tests

**Per Service:**
- RFC ingestion: Mock HTTP responses, validate parsing
- RFC parser: Test XML parsing, section extraction
- RFC chunking: Validate chunk boundaries
- RFC linker: Test pattern matching

**Coverage Target and Reporting:**
- Minimum 80% line coverage **per service and adapter** impacted by this RFC (ingestion, parsing, chunking, linking)
- The RFC database integration feature should maintain at least 80% aggregate coverage as reflected in the repository-wide Coveralls report
- Coverage is measured and reported via the existing unified CI workflows (service/adapter pytest runs with `pytest-cov`) and Coveralls integration; no separate coverage tooling is introduced for this feature

### Integration Tests

**End-to-End Workflows:**
1. Ingest RFC → Parse → Chunk → Embed → Search
2. Parse message → Detect RFC refs → Create links
3. Thread summary → Retrieve RFC context → Generate

**Test Data:**
- RFC 9000 (QUIC) - complex, multi-section
- RFC 2119 (Keywords) - short, normative

### Performance Tests

**Load Testing:**
- Simulate 100 concurrent searches
- Measure p50, p95, p99 latencies
- Validate under sustained load (1 hour)

---

## Operational Considerations

### Monitoring

**Key Metrics:**
- `rfc_ingestion_duration_seconds` - Time to ingest one RFC
- `rfc_parse_failures_total` - Failed RFC parses
- `rfc_search_latency_seconds` - Search query latency
- `rfc_chunks_total` - Total RFC chunks stored
- `rfc_links_created_total` - RFC-message links created

**Dashboards:**
- RFC Ingestion Status
- RFC Search Performance
- RFC-Message Linking Stats

### Alerting

**Critical Alerts:**
- RFC ingestion service down (>5min)
- RFC search latency >5s (p95)

**Warning Alerts:**
- RFC ingestion behind schedule (>24h lag)

### Backup and Recovery

**Backup Strategy:**
- MongoDB: Daily snapshots
- Qdrant: Weekly vector index backup

**Recovery Procedures:**
- RFC corpus: Re-ingest from RFC Editor (4-6 hours)

---

## Open Questions

### Technical

1. **Embedding Model Selection**
   - Use same model as mailing lists (consistency) or RFC-specific model?
   - **Recommendation**: Same model initially, evaluate later

2. **Chunking Strategy for Large Sections**
   - Fixed-size with overlap vs. semantic boundary detection?
   - **Recommendation**: Start with subsection boundaries

3. **Link Confidence Threshold**
   - What confidence score for automatic vs. suggested links?
   - **Recommendation**: >0.9 automatic, 0.7-0.9 suggested

### Product

1. **User Permissions**
   - Who can create/edit manual RFC-message links?
   - **Recommendation**: Authenticated users create, admins edit

2. **RFC Diff Viewer**
   - Priority for Phase 1?
   - **Recommendation**: Defer to post-launch

### Operational

1. **Ingestion Frequency**
   - Daily, weekly, or on-demand?
   - **Recommendation**: Weekly scheduled + manual trigger

2. **Storage Retention**
   - Keep all RFC versions or only latest?
   - **Recommendation**: Keep all (minimal storage cost)

---

## References

### IETF Resources

- [RFC Editor](https://www.rfc-editor.org/)
- [IETF Datatracker](https://datatracker.ietf.org/)
- [Datatracker API Documentation](https://datatracker.ietf.org/api/v1/)
- [RFC 2119: Key words for RFCs](https://www.rfc-editor.org/rfc/rfc2119.html)
- [RFC 7322: RFC Style Guide](https://www.rfc-editor.org/rfc/rfc7322.html)
- [XML2RFC Format](https://xml2rfc.tools.ietf.org/)

### Internal Documentation

- [Architecture overview](architecture/overview.md)
- [Schema overview](schemas/data-storage.md)
- [OBSERVABILITY_RFC.md](./OBSERVABILITY_RFC.md)
- [CONVENTIONS.md](../documents/CONVENTIONS.md)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-28 | Copilot Team | Initial draft |

