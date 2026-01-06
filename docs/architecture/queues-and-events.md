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

### Unified Per-Event Queue Names

All services now use the same queue names across both Azure Service Bus and RabbitMQ deployments:
- `archive.ingested` - Consumed by parsing service
- `json.parsed` - Consumed by chunking service
- `chunks.prepared` - Consumed by embedding service
- `embeddings.generated` - Consumed by orchestrator service
- `summarization.requested` - Consumed by summarization service
- `summary.complete` - Consumed by reporting service

This unified approach eliminates the need for environment-specific queue naming or auto-detection logic. All services use hardcoded per-event queue names that match the event routing keys.

## Queue Configuration per Deployment Type

Both Azure Service Bus and Docker Compose (RabbitMQ) use the same queue topology with per-event queue names. Services are configured identically across both environments.

### Example: Orchestrator Service

**Both Azure Service Bus and RabbitMQ:**
```bash
export MESSAGE_BUS_TYPE=azureservicebus  # or rabbitmq
```

The queue name is hardcoded to `embeddings.generated` in the service code and cannot be overridden via environment variables.

## Queue Lifecycle

### Pre-declared Queues

All queues are pre-declared before services start:

- **Azure Service Bus:** Queues are created via Bicep infrastructure templates (`infra/azure/modules/servicebus.bicep`)
- **RabbitMQ:** Queues are pre-declared in `infra/rabbitmq/definitions.json`

The pre-declared queues include all per-event input queues:
- **archive.ingested** - Parsing input
- **json.parsed** - Chunking input
- **chunks.prepared** - Embedding input
- **embeddings.generated** - Orchestrator input
- **summarization.requested** - Summarization input
- **summary.complete** - Reporting input

Plus failure/dead-letter queues for error handling and monitoring.

## Message Flow

```
Ingestion → archive.ingested queue → Parsing Service
    ↓
Parsing → routing_key: json.parsed → json.parsed queue → Chunking Service
    ↓
Chunking → routing_key: chunks.prepared → chunks.prepared queue → Embedding Service
    ↓
Embedding → routing_key: embeddings.generated → embeddings.generated queue → Orchestrator Service
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

In the current infrastructure, these failed event queues are pre-declared in
`infra/rabbitmq/definitions.json` to support monitoring and potential future
integrations. Note that without active consumers, these queues may accumulate
messages. We plan to revisit this by adding TTL-based dead-letter policies,
retry handlers, or removing unused failed queues from the default deployment
to prevent unbounded accumulation.

## Common Issues

### Issue: Messages accumulating in queues

**Symptom:** Queues like `chunks.prepared`, `embeddings.generated`, or `summary.complete` show growing message counts.

**Cause:** Service is not consuming from the queue (service not running, connection failed, or incorrect queue name).

**Solution:**
1. Verify service is running and connected to the message bus
2. Check service logs for connection errors
3. Verify the hardcoded queue_name in the service matches the expected queue

### Issue: Service can't consume messages

**Symptom:** Service starts but doesn't process events.

**Cause:** Service is connected but queue doesn't have the expected messages (check routing key or publisher).

**Solution:**
1. Verify the publisher is sending to the correct routing key
2. Confirm the queue is bound to the correct routing key (RabbitMQ only)
3. Check queue exists in Azure Service Bus or RabbitMQ management UI
4. Verify the service is subscribed to the correct event type

## Monitoring Queue Health

Use the RabbitMQ Management UI (`http://localhost:15672`) or Azure Service Bus explorer to monitor:
- **Ready messages** - Should drain to 0 when system is idle
- **Unacked messages** - Should be low (processing in progress)
- **Message rate** - Should balance publish/consume rates
- **Consumers** - Each service queue should have 1 active consumer

### Expected Queue States When Idle

| Queue | Ready Messages | Consumers |
|-------|---------------|-----------|
| archive.ingested | 0 | 1 |
| json.parsed | 0 | 1 |
| chunks.prepared | 0 | 1 |
| embeddings.generated | 0 | 1 |
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
