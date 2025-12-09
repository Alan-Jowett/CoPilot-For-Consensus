<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Data Storage Schema

This document defines the data storage schema for Copilot-for-Consensus, including document database collections, vector store structure, and the linkage between embeddings and source messages.

## Overview

The system uses two primary storage systems:
1. **Document Database (MongoDB/Cosmos DB)** - Stores structured message data, metadata, and summaries
2. **Vector Store (Qdrant/FAISS/Azure Cognitive Search)** - Stores embeddings with metadata for semantic search

## Document Database Schema

### Collection: `archives`
Stores metadata about ingested mailing list archives.

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `archive_id` | String (UUID) | Unique identifier for the archive | Primary Key |
| `source` | String | Source identifier (e.g., "ietf-quic") | Yes |
| `source_url` | String | URL or path to original archive | No |
| `format` | String | Archive format (e.g., "mbox") | No |
| `ingestion_date` | DateTime | When the archive was ingested | Yes |
| `message_count` | Integer | Number of messages in archive | No |
| `file_path` | String | Storage path for raw archive | No |
| `status` | String | Processing status (pending, processed, failed) | Yes |

**Indexes:**
- Primary: `archive_id`
- Secondary: `source`, `ingestion_date`, `status`

---

### Collection: `messages`
Stores parsed and normalized email messages.

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `message_id` | String | RFC 5322 Message-ID (globally unique) | Primary Key |
| `archive_id` | String (UUID) | Reference to parent archive | Yes |
| `thread_id` | String | Thread identifier (root message_id) | Yes |
| `in_reply_to` | String | Message-ID of parent message | Yes |
| `references` | Array[String] | List of referenced Message-IDs | No |
| `subject` | String | Email subject line | No |
| `from` | Object | Sender details (name, email) | No |
| `to` | Array[Object] | Recipients (name, email) | No |
| `cc` | Array[Object] | CC recipients | No |
| `date` | DateTime | Message timestamp | Yes |
| `body_raw` | String | Raw message body | No |
| `body_normalized` | String | Cleaned/normalized text | No |
| `body_html` | String | HTML content (if available) | No |
| `headers` | Object | Additional email headers | No |
| `attachments` | Array[Object] | Attachment metadata | No |
| `draft_mentions` | Array[String] | Mentioned RFC/draft identifiers | Yes |
| `created_at` | DateTime | Record creation timestamp | Yes |

**Indexes:**
- Primary: `message_id`
- Secondary: `archive_id`, `thread_id`, `date`, `in_reply_to`, `draft_mentions`, `created_at`

**Example Document:**
```json
{
  "message_id": "<20231015123456.ABC123@example.com>",
  "archive_id": "550e8400-e29b-41d4-a716-446655440000",
  "thread_id": "<20231015120000.XYZ789@example.com>",
  "in_reply_to": "<20231015120000.XYZ789@example.com>",
  "references": ["<20231015120000.XYZ789@example.com>"],
  "subject": "Re: QUIC connection migration concerns",
  "from": {"name": "Alice Developer", "email": "alice@example.com"},
  "date": "2023-10-15T12:34:56Z",
  "body_normalized": "I agree with the proposed approach...",
  "draft_mentions": ["draft-ietf-quic-transport-34"],
  "created_at": "2023-10-15T13:00:00Z"
}
```

---

### Collection: `chunks`
Stores text chunks derived from messages for embedding generation.

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `chunk_id` | String (UUID) | Unique identifier for chunk | Primary Key |
| `message_id` | String | Source message Message-ID | Yes |
| `thread_id` | String | Thread identifier | Yes |
| `chunk_index` | Integer | Sequential index within message (0-based) | No |
| `text` | String | Chunk text content | No |
| `token_count` | Integer | Approximate token count | No |
| `start_offset` | Integer | Character offset in original message | No |
| `end_offset` | Integer | End character offset | No |
| `overlap_with_previous` | Boolean | Whether chunk overlaps with previous | No |
| `metadata` | Object | Additional context (sender, date, subject) | No |
| `created_at` | DateTime | Chunk creation timestamp | Yes |
| `embedding_generated` | Boolean | Whether embedding exists in vector store | Yes |

**Indexes:**
- Primary: `chunk_id`
- Secondary: `message_id`, `thread_id`, `created_at`, `embedding_generated`

**Example Document:**
```json
{
  "chunk_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "message_id": "<20231015123456.ABC123@example.com>",
  "thread_id": "<20231015120000.XYZ789@example.com>",
  "chunk_index": 0,
  "text": "I agree with the proposed approach for connection migration. The key concern is...",
  "token_count": 128,
  "start_offset": 0,
  "end_offset": 512,
  "overlap_with_previous": false,
  "metadata": {
    "sender": "alice@example.com",
    "date": "2023-10-15T12:34:56Z",
    "subject": "Re: QUIC connection migration concerns"
  },
  "created_at": "2023-10-15T13:05:00Z",
  "embedding_generated": true
}
```

---

### Collection: `threads`
Stores aggregated thread metadata for quick retrieval.

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `thread_id` | String | Thread identifier (root message_id) | Primary Key |
| `archive_id` | String (UUID) | Reference to parent archive | Yes |
| `subject` | String | Thread subject (from root message) | No |
| `participants` | Array[Object] | List of participants (name, email) | No |
| `message_count` | Integer | Number of messages in thread | No |
| `first_message_date` | DateTime | Timestamp of first message | Yes |
| `last_message_date` | DateTime | Timestamp of most recent message | Yes |
| `draft_mentions` | Array[String] | All drafts mentioned in thread | Yes |
| `has_consensus` | Boolean | Whether consensus was detected | Yes |
| `consensus_type` | String | Type (agreement, dissent, mixed) | No |
| `summary_id` | String (UUID) | Reference to generated summary | Yes |
| `created_at` | DateTime | Thread record creation | Yes |

**Indexes:**
- Primary: `thread_id`
- Secondary: `archive_id`, `first_message_date`, `last_message_date`, `draft_mentions`, `has_consensus`, `summary_id`, `created_at`

---

### Collection: `summaries`
Stores generated summaries and reports.

| Field | Type | Description | Indexed |
|-------|------|-------------|---------|
| `summary_id` | String (UUID) | Unique identifier for summary | Primary Key |
| `thread_id` | String | Associated thread (null for multi-thread summaries) | Yes |
| `summary_type` | String | Type (thread, weekly, consensus, draft-focused) | Yes |
| `title` | String | Summary title | No |
| `content_markdown` | String | Summary content in Markdown | No |
| `content_html` | String | Summary content in HTML | No |
| `citations` | Array[Object] | References to source messages/chunks | No |
| `generated_by` | String | LLM model identifier | No |
| `generated_at` | DateTime | Generation timestamp | Yes |
| `metadata` | Object | Additional context (date range, participants) | No |

**Indexes:**
- Primary: `summary_id`
- Secondary: `thread_id`, `summary_type`, `generated_at`

**Citation Object Structure:**
```json
{
  "chunk_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "message_id": "<20231015123456.ABC123@example.com>",
  "quote": "I agree with the proposed approach...",
  "relevance_score": 0.92
}
```

---

## Vector Store Schema

### Vector Collection: `message_embeddings`
Stores embeddings with metadata for semantic search and retrieval-augmented generation (RAG).

#### Vector Structure

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Same as `chunk_id` from document DB |
| `vector` | Array[Float] | Embedding vector (e.g., 384 or 1536 dimensions) |
| `payload` | Object | Metadata payload (see below) |

#### Payload Schema

The payload contains metadata that links the embedding back to the source message and enables filtering during search.

```json
{
  "chunk_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "message_id": "<20231015123456.ABC123@example.com>",
  "thread_id": "<20231015120000.XYZ789@example.com>",
  "archive_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunk_index": 0,
  "text": "I agree with the proposed approach for connection migration...",
  "sender": "alice@example.com",
  "sender_name": "Alice Developer",
  "date": "2023-10-15T12:34:56Z",
  "subject": "Re: QUIC connection migration concerns",
  "draft_mentions": ["draft-ietf-quic-transport-34"],
  "token_count": 128,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_date": "2023-10-15T13:10:00Z"
}
```

#### Payload Field Descriptions

| Field | Type | Purpose |
|-------|------|---------|
| `chunk_id` | String | Links to `chunks` collection in document DB |
| `message_id` | String | Links to `messages` collection; enables message-level retrieval |
| `thread_id` | String | Enables thread-level filtering and context |
| `archive_id` | String | Enables archive-level filtering |
| `chunk_index` | Integer | Preserves order within message |
| `text` | String | Actual chunk content for display/verification |
| `sender` | String | Enables filtering by author |
| `sender_name` | String | Human-readable author name |
| `date` | DateTime | Enables temporal filtering |
| `subject` | String | Provides context in search results |
| `draft_mentions` | Array[String] | Enables filtering by mentioned drafts/RFCs |
| `token_count` | Integer | Used for context window management |
| `embedding_model` | String | Tracks which model generated embedding |
| `embedding_date` | DateTime | Audit trail for embeddings |

---

## Linking Embeddings to Source Messages

### Forward Linkage (Embedding → Message)

Each vector in the vector store contains metadata that directly references:
1. **`chunk_id`** → Links to `chunks` collection
2. **`message_id`** → Links to `messages` collection
3. **`thread_id`** → Links to `threads` collection

**Retrieval Flow:**
```
Vector Search → Embedding Payload → chunk_id → chunks.message_id → messages → Full Message
```

**Example Query:**
```python
# 1. Perform vector similarity search
search_results = vector_store.search(
    query_embedding,
    limit=10,
    query_filter={"draft_mentions": "draft-ietf-quic-transport-34"}
)

# 2. Extract chunk_ids from results
chunk_ids = [r.payload["chunk_id"] for r in search_results]

# 3. Retrieve full chunks from document DB
chunks = db.chunks.find({"chunk_id": {"$in": chunk_ids}})

# 4. Retrieve full messages
message_ids = [c["message_id"] for c in chunks]
messages = db.messages.find({"message_id": {"$in": message_ids}})
```

### Reverse Linkage (Message → Embedding)

To find all embeddings for a given message:

**Via Document DB:**
```python
# 1. Find all chunks for a message
chunks = list(db.chunks.find({
    "message_id": "<20231015123456.ABC123@example.com>"
}))

# 2. Extract chunk_ids
chunk_ids = [c["chunk_id"] for c in chunks]

# 3. Retrieve embeddings from vector store
embeddings = vector_store.retrieve(chunk_ids)
```

**Via Vector Store Filter:**
```python
# Direct filter on vector store payload
embeddings = vector_store.scroll(
    scroll_filter={
        "message_id": "<20231015123456.ABC123@example.com>"
    }
)
```

---

## Key Relationships

### Entity-Relationship Diagram (Conceptual)

```
archives (1) ──< (N) messages
                    │
                    │ (1)
                    │
                    ├─< (N) chunks ───> (1:1) vector_embeddings
                    │                        (via chunk_id)
                    │
                    │ (N)
                    └─> (1) threads
                           │
                           │ (1)
                           └─> (1) summaries
```

### Primary Relationships

1. **Archive → Messages**: One archive contains many messages
   - FK: `messages.archive_id` → `archives.archive_id`

2. **Message → Chunks**: One message splits into many chunks
   - FK: `chunks.message_id` → `messages.message_id`

3. **Chunk → Embedding**: One chunk has one embedding (1:1)
   - FK: `vector_store.id` = `chunks.chunk_id`

4. **Thread → Messages**: One thread aggregates many messages
   - FK: `messages.thread_id` → `threads.thread_id`

5. **Thread → Summary**: One thread may have one summary
   - FK: `threads.summary_id` → `summaries.summary_id`

6. **Summary → Citations**: One summary references many chunks
   - Embedded: `summaries.citations[].chunk_id` → `chunks.chunk_id`

---

## Search and Retrieval Patterns

### Pattern 1: Semantic Search with Full Context

**Use Case:** Find relevant messages about a topic

```python
# 1. Vector search
results = vector_store.search(
    query_embedding,
    limit=20,
    query_filter={"date": {"$gte": "2023-10-01"}}
)

# 2. Enrich with full message context
enriched_results = []
for result in results:
    chunk = db.chunks.find_one({"chunk_id": result.id})
    message = db.messages.find_one({"message_id": chunk["message_id"]})
    thread = db.threads.find_one({"thread_id": message["thread_id"]})
    
    enriched_results.append({
        **result.__dict__,
        "chunk": chunk["text"],
        "message": message["body_normalized"],
        "thread": thread["subject"],
        "sender": message["from"]
    })
```

### Pattern 2: Thread-Level Retrieval

**Use Case:** Get all embeddings for a thread

```python
# Option A: Via document DB
messages = list(db.messages.find({
    "thread_id": "<20231015120000.XYZ789@example.com>"
}))
message_ids = [m["message_id"] for m in messages]
chunks = list(db.chunks.find({"message_id": {"$in": message_ids}}))
embeddings = vector_store.retrieve([c["chunk_id"] for c in chunks])

# Option B: Direct vector store filter
embeddings = vector_store.scroll(
    scroll_filter={"thread_id": "<20231015120000.XYZ789@example.com>"}
)
```

### Pattern 3: Citation Verification

**Use Case:** Verify summary citations link to source

```python
summary = db.summaries.find_one({"summary_id": "..."})

for citation in summary["citations"]:
    # Retrieve chunk
    chunk = db.chunks.find_one({"chunk_id": citation["chunk_id"]})
    
    # Retrieve original message
    message = db.messages.find_one({"message_id": chunk["message_id"]})
    
    # Verify quote appears in chunk
    is_valid = citation["quote"] in chunk["text"]
    
    print(f"Citation valid: {is_valid}")
    print(f"Source: {message['from']['email']} on {message['date']}")
```

---

## Indexing Strategy

### Document Database Indexes

**MongoDB Index Definitions:**

```python
# archives collection
db.archives.create_index([("archive_id", 1)], unique=True)
db.archives.create_index([("source", 1), ("ingestion_date", -1)])
db.archives.create_index([("status", 1)])

# messages collection
db.messages.create_index([("message_id", 1)], unique=True)
db.messages.create_index([("archive_id", 1), ("date", -1)])
db.messages.create_index([("thread_id", 1), ("date", 1)])
db.messages.create_index([("draft_mentions", 1)])
db.messages.create_index([("from.email", 1), ("date", -1)])

# chunks collection
db.chunks.create_index([("chunk_id", 1)], unique=True)
db.chunks.create_index([("message_id", 1), ("chunk_index", 1)])
db.chunks.create_index([("thread_id", 1)])
db.chunks.create_index([("embedding_generated", 1), ("created_at", 1)])

# threads collection
db.threads.create_index([("thread_id", 1)], unique=True)
db.threads.create_index([("first_message_date", -1)])
db.threads.create_index([("draft_mentions", 1)])
db.threads.create_index([("has_consensus", 1), ("last_message_date", -1)])

# summaries collection
db.summaries.create_index([("summary_id", 1)], unique=True)
db.summaries.create_index([("thread_id", 1)])
db.summaries.create_index([("summary_type", 1), ("generated_at", -1)])
```

### Vector Store Indexes

**Qdrant Payload Indexes:**

```python
# Create payload indexes for filtering
client.create_payload_index(
    collection_name="message_embeddings",
    field_name="message_id",
    field_schema="keyword"
)

client.create_payload_index(
    collection_name="message_embeddings",
    field_name="thread_id",
    field_schema="keyword"
)

client.create_payload_index(
    collection_name="message_embeddings",
    field_name="date",
    field_schema="datetime"
)

client.create_payload_index(
    collection_name="message_embeddings",
    field_name="draft_mentions",
    field_schema="keyword"
)

client.create_payload_index(
    collection_name="message_embeddings",
    field_name="sender",
    field_schema="keyword"
)
```

---

## Data Integrity Constraints

### Referential Integrity

1. **Chunks must reference valid messages**
   - Before inserting chunk: Verify `message_id` exists in `messages` collection
   
2. **Embeddings must reference valid chunks**
   - Vector store `id` must match existing `chunk_id` in `chunks` collection
   
3. **Summary citations must reference valid chunks**
   - All `summaries.citations[].chunk_id` must exist in `chunks` collection

### Consistency Checks

**Periodic Validation Queries:**

```python
# Find chunks without embeddings
for chunk in db.chunks.find({"embedding_generated": True}):
    exists = vector_store.retrieve([chunk["chunk_id"]])
    if not exists or len(exists) == 0:
        print(f"Missing embedding for chunk: {chunk['chunk_id']}")

# Find orphaned embeddings (no corresponding chunk)
all_embedding_ids = vector_store.list_all_ids()
chunk_ids = db.chunks.distinct("chunk_id")
orphaned = [id for id in all_embedding_ids if id not in chunk_ids]
print(f"Orphaned embeddings: {len(orphaned)}")

# Find messages without chunks
for message in db.messages.find({}):
    chunk_count = db.chunks.count_documents({
        "message_id": message["message_id"]
    })
    if chunk_count == 0:
        print(f"Message has no chunks: {message['message_id']}")
```

---

## Migration and Versioning

### Schema Version Tracking

Add a `schema_version` field to each collection to track schema evolution:

```python
# Example: messages collection
{
    "schema_version": "1.0.0",
    "message_id": "...",
    # ... other fields
}
```

### Backward Compatibility

When updating schemas:
1. Add new fields as optional
2. Maintain old fields during transition period
3. Use migration scripts to backfill data
4. Version vector store collections separately

**Example Migration:**

```python
# Add new field to existing documents
db.messages.update_many(
    {"draft_mentions": {"$exists": False}},
    {"$set": {"draft_mentions": [], "schema_version": "1.1.0"}}
)
```

---

## Performance Considerations

### Query Optimization

1. **Use projection to limit returned fields**
   ```python
   db.messages.find(
       {"thread_id": "..."},
       {"message_id": 1, "subject": 1, "date": 1, "_id": 0}
   )
   ```

2. **Batch operations for embeddings**
   ```python
   # Retrieve multiple embeddings in one call
   embeddings = vector_store.retrieve(chunk_ids)
   ```

3. **Cache frequently accessed threads**
   - Cache thread metadata and message lists in Redis
   - Invalidate on new messages

4. **Limit vector search results**
   - Use `limit` parameter to constrain result set
   - Implement pagination for large result sets

### Storage Estimates

**For 100,000 messages:**

| Component | Size Estimate |
|-----------|---------------|
| Messages (avg 5KB each) | ~500 MB |
| Chunks (avg 512 bytes, 3 per message) | ~150 MB |
| Vectors (384-dim, 3 per message) | ~460 MB |
| Total | ~1.1 GB |

**Scaling Factor:** ~11 MB per 1,000 messages
