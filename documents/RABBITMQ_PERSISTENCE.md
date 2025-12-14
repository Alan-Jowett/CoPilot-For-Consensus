# RabbitMQ Message Persistence

## Overview

This document describes how RabbitMQ is configured for message persistence in the Copilot-for-Consensus system to ensure guaranteed forward progress for email processing and other critical workflows.

## Configuration

### Queue Durability

All queues in the system are configured as **durable** queues. This means:
- Queues survive RabbitMQ broker restarts
- Queue metadata (bindings, routing keys) is persisted to disk
- Queues are not automatically deleted when consumers disconnect

Configuration in `infra/rabbitmq/definitions.json`:
```json
{
  "name": "archive.ingested",
  "vhost": "/",
  "durable": true,
  "auto_delete": false,
  "arguments": {}
}
```

### Exchange Durability

The main exchange `copilot.events` is configured as **durable**:
```json
{
  "name": "copilot.events",
  "vhost": "/",
  "type": "topic",
  "durable": true,
  "auto_delete": false,
  "internal": false,
  "arguments": {}
}
```

### Message Persistence

All messages published through `RabbitMQPublisher` are marked as **persistent** (delivery_mode=2):

```python
self.channel.basic_publish(
    exchange=exchange,
    routing_key=routing_key,
    body=json.dumps(event),
    properties=pika.BasicProperties(
        delivery_mode=2,  # Make messages persistent
        content_type="application/json",
    ),
    mandatory=True,
)
```

This ensures messages are written to disk and survive broker restarts.

## Guarantees

With this configuration, the system provides the following guarantees:

1. **Messages survive consumer downtime**: If a consumer is offline when a message is published, the message remains in the queue until the consumer comes back online.

2. **Messages survive broker restarts**: If the RabbitMQ broker restarts, all queues and their messages are restored from disk.

3. **No message loss on consumer failure**: If a consumer crashes while processing a message, the message is requeued (unless explicitly acknowledged).

4. **Forward progress**: Email processing and other workflows can make forward progress even if components are temporarily unavailable.

## Message Acknowledgment

Subscribers use **manual acknowledgment** (auto_ack=False by default) to ensure messages are only removed from queues after successful processing:

```python
subscriber = RabbitMQSubscriber(
    host=config["host"],
    port=config["port"],
    queue_name="archive.ingested",
    queue_durable=True,
    auto_ack=False,  # Manual acknowledgment
)
```

## Verification

### Verify Configuration File

Check that `definitions.json` has all queues and exchanges marked as durable:

```bash
python scripts/verify_rabbitmq_persistence.py --skip-live-check
```

### Verify Live RabbitMQ Server

Check that the running RabbitMQ instance has durable queues and exchanges:

```bash
python scripts/verify_rabbitmq_persistence.py
```

This connects to the RabbitMQ server and verifies:
- All queues are durable
- All exchanges are durable
- Configuration matches `definitions.json`

### Integration Tests

Run the persistence integration tests to verify messages survive consumer downtime:

```bash
cd adapters/copilot_events
pytest tests/test_integration_rabbitmq.py::TestRabbitMQPersistence -v
```

These tests:
1. Publish messages before starting a consumer
2. Verify messages are delivered when consumer starts
3. Test queue durability across connection/disconnection cycles

## Performance Considerations

Persistent messages have some performance overhead compared to transient messages:

- Messages are written to disk before acknowledgment
- Queues maintain both in-memory and on-disk state
- Recovery after broker restart takes longer with many persistent messages

For this application, **correctness and guaranteed delivery are more important than raw throughput**, so the persistence overhead is acceptable.

## Troubleshooting

### Messages Not Persisting

If messages are being lost:

1. Check queue configuration:
   ```bash
   python scripts/verify_rabbitmq_persistence.py
   ```

2. Verify publisher is using delivery_mode=2:
   ```python
   # In RabbitMQPublisher.publish()
   properties=pika.BasicProperties(delivery_mode=2)
   ```

3. Check RabbitMQ logs for errors:
   ```bash
   docker compose logs messagebus
   ```

### Queue Not Durable

If a queue is not durable, update `definitions.json` and restart RabbitMQ:

```bash
docker compose restart messagebus
```

Note: RabbitMQ will load definitions from `definitions.json` on startup.

## References

- [RabbitMQ Persistence Configuration](https://www.rabbitmq.com/persistence-conf.html)
- [RabbitMQ Queues](https://www.rabbitmq.com/queues.html)
- [RabbitMQ Publisher Confirms](https://www.rabbitmq.com/confirms.html)
