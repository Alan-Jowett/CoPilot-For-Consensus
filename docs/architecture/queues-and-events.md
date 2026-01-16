<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Queue Architecture

This document explains the event delivery architecture for both RabbitMQ (Docker Compose) and Azure Service Bus deployments.

## Overview

The system uses message queues to distribute events between microservices:
- **RabbitMQ**: Uses a topic exchange (`copilot.events`) with routing keys and named durable queues
- **Azure Service Bus**: Uses a shared topic (`copilot.events`) with one subscription per service (fan-out)

Services subscribe to events they process via:

- RabbitMQ: a durable queue per service input, bound to routing keys
- Azure Service Bus: a durable subscription per service on the shared topic

## Naming & Routing Strategy

### Routing Keys (Cross-Bus Convention)

Routing keys are stable identifiers for the pipeline:

- `archive.ingested` - Parsing input
- `json.parsed` - Chunking input
- `chunks.prepared` - Embedding input
- `embeddings.generated` - Orchestrator input
- `summarization.requested` - Summarization input
- `summary.complete` - Reporting input

This unified approach keeps the pipeline semantics consistent across message bus backends.

## Queue Configuration per Deployment Type

RabbitMQ and Azure Service Bus use different physical entities, but share the same logical routing keys.

### Example: Orchestrator Service

**Both Azure Service Bus and RabbitMQ:**
```bash
export MESSAGE_BUS_TYPE=azure_service_bus  # or rabbitmq
```

The service subscribes to `EmbeddingsGenerated` events and publishes `SummarizationRequested` events. The physical queue/subscription identity is service-owned and not intended as a deployment-time setting.

## Queue Lifecycle

### Pre-declared Queues

All delivery entities are pre-declared before services start:

- **Azure Service Bus:** Topic + subscriptions are created via Bicep (`infra/azure/modules/servicebus.bicep`)
- **RabbitMQ:** Exchange + queues/bindings are defined in `infra/rabbitmq/definitions.json`

RabbitMQ additionally defines named queues/bindings for failure/dead-letter handling and monitoring.

## Message Flow

```
In all deployments, publishers publish to `exchange="copilot.events"` with a stable routing key.

- RabbitMQ: routing key drives which queues receive the message (bindings)
- Azure Service Bus: routing key is stored in the message `subject` and `application_properties` for observability; delivery is via per-service subscriptions on the shared topic
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

**Cause:** A consumer is not running/connected (or the delivery entity is missing).

**Solution:**
1. Verify service is running and connected to the message bus
2. Check service logs for connection errors
3. For Azure Service Bus, verify the topic `copilot.events` exists and the service subscription exists

### Issue: Service can't consume messages

**Symptom:** Service starts but doesn't process events.

**Cause:** Service is connected but queue doesn't have the expected messages (check routing key or publisher).

**Solution:**
1. Verify the publisher is sending to the correct routing key
2. Confirm the queue is bound to the correct routing key (RabbitMQ only)
3. Check the entity exists in Azure Service Bus (topic/subscription) or RabbitMQ management UI
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

For Azure Service Bus deployments, add a new event type by publishing it to the shared topic. If you need fan-out to a new consumer service, add a new subscription for that service in `infra/azure/modules/servicebus.bicep`.

## References

- [RabbitMQ Topic Exchange Tutorial](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)
- [RabbitMQ Queues Documentation](https://www.rabbitmq.com/queues.html)
- [Schema index](../schemas/README.md)
- [copilot_message_bus Adapter README](../../adapters/copilot_message_bus/README.md)
