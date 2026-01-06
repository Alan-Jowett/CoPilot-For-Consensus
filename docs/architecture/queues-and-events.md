<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Queue Architecture

This document explains the queue architecture for both RabbitMQ (Docker Compose) and Azure Service Bus deployments.

## Overview

The system uses message queues to distribute events between microservices:
- **RabbitMQ**: Uses a topic exchange (`copilot.events`) with routing keys and named durable queues
- **Azure Service Bus**: Uses queues directly as the primary delivery mechanism

Services subscribe to queues that match the input events they process, allowing for flexible deployment across both message bus types.

## Queue Naming Strategy

### Service Input Queues (Primary Pattern)

Each service subscribes to the queue containing events it processes:
- `archive.ingested` - Consumed by parsing service
- `json.parsed` - Consumed by chunking service
- `chunks.prepared` - Consumed by embedding service
- `embeddings.generated` - Consumed by orchestrator service
- `summarization.requested` - Consumed by summarization service
- `summary.complete` - Consumed by reporting service

### RabbitMQ Custom Queue Names (Legacy Pattern)

RabbitMQ deployments may use custom queue names for services that need to subscribe to multiple routing keys:
- `embedding-service` - Embedding service (subscribes to `chunks.prepared` routing key)
- `orchestrator-service` - Orchestrator service (subscribes to `embeddings.generated` routing key)

This is controlled via the `ORCHESTRATOR_QUEUE_NAME` and similar environment variables, allowing the same codebase to work across both deployment types.

## Queue Configuration per Deployment Type

### Azure Service Bus Deployment

Uses direct queue names matching the routing keys in RabbitMQ:

```bash
# Orchestrator configuration for Azure Service Bus
export MESSAGE_BUS_TYPE=azureservicebus
export ORCHESTRATOR_QUEUE_NAME=embeddings.generated  # Uses input queue directly
```

### RabbitMQ Deployment (Docker Compose)

Uses topic exchanges with custom service queue names:

```bash
# Orchestrator configuration for RabbitMQ
export MESSAGE_BUS_TYPE=rabbitmq
export ORCHESTRATOR_QUEUE_NAME=orchestrator-service  # Custom service queue
```

Or omit `ORCHESTRATOR_QUEUE_NAME` to use auto-detection based on `MESSAGE_BUS_TYPE`.

## Queue Lifecycle

### Dynamic Queue Creation

Queues not in `definitions.json` are created dynamically when services start:

```python
subscriber = create_subscriber(
    message_bus_type="rabbitmq",
    host="messagebus",
    queue_name="embedding-service",  # Creates queue on connect
)
subscriber.connect()
subscriber.subscribe(
    event_type="ChunksPrepared",
    routing_key="chunks.prepared",  # Binds queue to this routing key
)
```

### Pre-declared Queues

The `infra/rabbitmq/definitions.json` file pre-declares essential queues for RabbitMQ deployments:
- **archive.ingested** - First stage (parsing input)
- **json.parsed** - Second stage (chunking input)
- **summarization.requested** - Summarization input
- **summary.complete** - Reporting input

These are declared upfront to:
- Ensure queues exist before services start
- Prevent message loss during service restarts
- Provide consistent queue configuration (durable, non-auto-delete)

For Azure Service Bus, all queues are pre-created via Bicep infrastructure templates.

## Message Flow

```
Ingestion → archive.ingested queue → Parsing Service
    ↓
Parsing → routing_key: json.parsed → json.parsed queue → Chunking Service
    ↓
Chunking → routing_key: chunks.prepared → embedding-service queue → Embedding Service
    ↓
Embedding → routing_key: embeddings.generated → orchestrator-service queue → Orchestrator Service
    ↓
Orchestrator → routing_key: summarization.requested → summarization.requested queue → Summarization Service
    ↓
Summarization → routing_key: summary.complete → summary.complete queue → Reporting Service
    ↓
Reporting → routing_key: report.published → (terminus event, no consumer)
```

## Terminus Events

Some events represent the **end of a processing pipeline** and have no consumers:
- `report.published` - Final output notification
- `*.failed` events - Error logging/monitoring

These events are **not bound to queues** in definitions.json because:
1. They would accumulate messages indefinitely without consumers
2. They are intended for optional external integrations (webhooks, monitoring)
3. Services can create temporary queues to monitor them if needed

## Failed Event Queues

The system currently does **not** have consumers for `*.failed` events:
- `archive.ingestion.failed`
- `parsing.failed`
- `chunking.failed`
- `embedding.generation.failed`
- `orchestration.failed`
- `summarization.failed`
- `report.delivery.failed`

These are **intentionally not pre-declared** in definitions.json to prevent unbounded message accumulation. Future implementations may add:
- Dead-letter queues with TTL
- Error handling/retry services
- Monitoring/alerting integrations

## Common Issues

### Issue: Messages accumulating in unused queues

**Symptom:** Queues like `chunks.prepared`, `embeddings.generated`, or `report.published` show growing message counts.

**Cause:** Duplicate queue definitions in `definitions.json` that have no active consumers.

**Solution:** Remove unused queue declarations from `definitions.json`. Only declare queues that have active consumers.

### Issue: Service can't consume messages

**Symptom:** Service starts but doesn't process events.

**Cause:** Service queue name doesn't match or isn't bound to the correct routing key.

**Solution:**
1. Check service code for `queue_name` parameter in `create_subscriber()`
2. Verify queue binding in `.subscribe()` matches the published routing_key
3. Check RabbitMQ management UI to confirm binding exists

## Monitoring Queue Health

Use the RabbitMQ Management UI (`http://localhost:15672`) to monitor:
- **Ready messages** - Should drain to 0 when system is idle
- **Unacked messages** - Should be low (processing in progress)
- **Message rate** - Should balance publish/consume rates
- **Consumers** - Each service queue should have 1 active consumer

**Note on Grafana Dashboards:** Some Grafana dashboards may reference old queue names like `chunks.prepared`, `embeddings.generated`, and `report.published`. These queries will return no data since those queues no longer exist. To monitor the actual message flow, use the service queue names instead:
- `embedding-service` instead of `chunks.prepared`
- `orchestrator-service` instead of `embeddings.generated`
- For `report.published` events, monitor the `summary.complete` queue consumption rate

### Expected Queue States When Idle

| Queue | Ready Messages | Consumers |
|-------|---------------|-----------|
| archive.ingested | 0 | 1 |
| json.parsed | 0 | 1 |
| embedding-service | 0 | 1 |
| orchestrator-service | 0 | 1 |
| summarization.requested | 0 | 1 |
| summary.complete | 0 | 1 |

## Adding New Event Types

When adding new events to the pipeline:

1. **Publish with routing key:**
   ```python
   publisher.publish(
       exchange="copilot.events",
       routing_key="my.new.event",
       event=event.to_dict()
   )
   ```

2. **Consumer creates queue and binds:**
   ```python
   subscriber = create_subscriber(
       queue_name="my-service-queue"
   )
   subscriber.subscribe(
       event_type="MyNewEvent",
       routing_key="my.new.event",
       callback=handle_event
   )
   ```

3. **DO NOT add to definitions.json** unless the queue matches the routing key AND will have an active consumer.

## References

- [RabbitMQ Topic Exchange Tutorial](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)
- [RabbitMQ Queues Documentation](https://www.rabbitmq.com/queues.html)
- [Schema index](../schemas/README.md)
- [copilot_events Adapter README](../../adapters/copilot_events/README.md)
