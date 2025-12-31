<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Cosmos DB Design and Collections Strategy

## Overview

The Copilot for Consensus deployment uses Azure Cosmos DB for NoSQL (SQL API) as the primary document store. This document describes the database structure, collection strategy, and design decisions.

## Database Structure

### Database: `copilot`
- **Autoscale throughput**: Configured via `cosmosDbAutoscaleMinRu` and `cosmosDbAutoscaleMaxRu` parameters
- **Consistency level**: Session (default)
- **Multi-region**: Optional (controlled by `enableMultiRegionCosmos` parameter)

### Container: `documents`
- **Partition key**: `/collection`
- **Description**: Single multi-collection container storing all document types

## Multi-Collection Pattern

Instead of creating separate containers for each document type, we use a **single container with logical collections** approach. All document types are stored in the same container, differentiated by a `collection` field that also serves as the partition key.

### Logical Collections

The following logical collections are stored in the `documents` container:

1. **archives**: Raw email archive metadata
   - Schema: `/documents/schemas/documents/v1/archives.schema.json`
   - Common queries: by source, ingestion_date, status

2. **messages**: Individual email messages extracted from archives
   - Schema: `/documents/schemas/documents/v1/messages.schema.json`
   - Common queries: by message_id, archive_id, thread_id, date

3. **chunks**: Semantic chunks generated from messages
   - Schema: `/documents/schemas/documents/v1/chunks.schema.json`
   - Common queries: by message_id, thread_id, embedding_generated

4. **threads**: Email conversation threads
   - Schema: `/documents/schemas/documents/v1/threads.schema.json`
   - Common queries: by archive_id, date ranges, draft_mentions, consensus flags

5. **summaries**: Generated summaries for threads
   - Schema: `/documents/schemas/documents/v1/summaries.schema.json`
   - Common queries: by thread_id, summary_type, generated_at

### Document Structure Example

```json
{
  "id": "unique-document-id",
  "collection": "messages",
  "_etag": "...",
  "_ts": 1234567890,
  "message_id": "msg-123",
  "archive_id": "arch-456",
  "thread_id": "thread-789",
  "date": "2025-01-15T10:30:00Z",
  "subject": "Consensus call discussion",
  "...": "other message fields"
}
```

## Design Benefits

### Advantages of Single Container Approach

1. **Simplified throughput management**: All collections share a single RU budget, simplifying capacity planning and cost optimization
2. **Cross-collection queries**: Enables efficient queries that span multiple collection types (e.g., joining messages with threads)
3. **Cross-collection transactions**: Supports transactional updates across different document types within the same partition
4. **Lower cost**: Reduces minimum RU requirements (one container minimum vs. multiple container minimums)
5. **Simplified deployment**: One container to provision and manage

### Trade-offs

1. **Shared partition key space**: All collections must use the same partition key strategy (`/collection`)
2. **Shared indexing policy**: Cannot configure different indexing policies per collection type
3. **Shared TTL**: Cannot set different Time-To-Live policies per collection
4. **Hot partition risk**: If query patterns heavily favor one collection type, it could create hot partitions

## Indexing Strategy

The container uses **composite indexes** optimized for common query patterns across all collections:

### Archives Queries
- `collection + source + ingestion_date` (descending)

### Messages Queries
- `collection + archive_id + date` (descending)
- `collection + thread_id + date` (descending)

### Threads Queries
- `collection + archive_id + last_message_date` (descending)

### Summaries Queries
- `collection + thread_id + generated_at` (descending)

### Chunks Queries
- `collection + message_id + sequence` (ascending)

All composite indexes include the `collection` field first to ensure efficient partition-scoped queries.

## Partition Strategy

### Partition Key: `/collection`

Using the collection name as the partition key provides:

1. **Natural partitioning**: Documents of the same type are co-located
2. **Predictable distribution**: Each collection type becomes a logical partition
3. **Efficient collection-scoped queries**: Queries within a single collection type are automatically partition-scoped

### Partition Considerations

- **Balance**: Ensure roughly equal distribution of operations across collection types
- **Avoid hot partitions**: Monitor if one collection type receives disproportionate traffic
- **Scale limits**: Each logical partition (collection) can scale to 20GB and 10,000 RU/s

If a single collection type exceeds these limits, consider:
1. Migrating to a more granular partition key (e.g., date-based or hash-based)
2. Moving that collection to a dedicated container with a custom partition key

## Throughput Configuration

### Development Environment
- **Minimum RU/s**: 400 (default)
- **Maximum RU/s**: 1,000 (default)
- **Mode**: Autoscale (database-level)

### Staging Environment
- **Minimum RU/s**: 1,000
- **Maximum RU/s**: 2,000
- **Mode**: Autoscale (database-level)

### Production Environment
- **Minimum RU/s**: 4,000 (recommended)
- **Maximum RU/s**: 10,000+ (adjust based on load)
- **Mode**: Autoscale (database-level)

### Cost Optimization

1. Use **autoscale throughput** (not provisioned) to automatically scale based on demand
2. Set `cosmosDbAutoscaleMinRu` to the lowest acceptable baseline
3. Set `cosmosDbAutoscaleMaxRu` to handle peak traffic (10x minimum)
4. Monitor RU consumption and adjust parameters as needed

## Migration Path

### When to Consider Separate Containers

If the application grows to the point where:

1. Individual collections exceed 20GB or 10,000 RU/s
2. Different collections require different TTL policies
3. Different collections need distinct indexing strategies
4. Hot partition issues arise

Then migrate to separate containers:

```
copilot/
├── archives        (partition key: /source)
├── messages        (partition key: /thread_id)
├── chunks          (partition key: /message_id)
├── threads         (partition key: /id)
└── summaries       (partition key: /thread_id)
```

This migration can be done incrementally using Azure Data Factory or custom migration scripts.

## Monitoring

### Key Metrics to Monitor

1. **RU consumption per collection**: Track which collections consume the most RUs
2. **Partition distribution**: Ensure operations are evenly distributed across collections
3. **Hot partitions**: Watch for 429 (rate limiting) errors on specific collections
4. **Storage per collection**: Monitor growth toward the 20GB partition limit
5. **Query performance**: Track P95/P99 latencies per collection type

### Alerting Thresholds

- **RU utilization > 80%**: Consider increasing `cosmosDbAutoscaleMaxRu`
- **429 errors > 1%**: Investigate partition hot spots or increase throughput
- **Query latency P95 > 100ms**: Review indexing policy and query patterns

## References

- [Cosmos DB Partitioning Best Practices](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview)
- [Cosmos DB Indexing Policies](https://learn.microsoft.com/en-us/azure/cosmos-db/index-policy)
- [Cosmos DB Autoscale Throughput](https://learn.microsoft.com/en-us/azure/cosmos-db/provision-throughput-autoscale)
- Schema definitions: `/documents/schemas/documents/v1/`
- Collection configuration: `/documents/schemas/documents/collections.config.json`
