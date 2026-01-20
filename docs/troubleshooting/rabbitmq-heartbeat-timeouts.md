# RabbitMQ Heartbeat Configuration

## Overview

This document explains the RabbitMQ heartbeat configuration and how to troubleshoot connection timeout issues.

## Problem

RabbitMQ uses heartbeat frames to detect broken TCP connections between clients and the server. When a client fails to send heartbeats within the configured timeout period, RabbitMQ closes the connection with an error like:

```
missed heartbeats from client, timeout: 60s
```

## Root Causes

Heartbeat timeouts can occur due to:

1. **CPU Starvation**: Heavy processing in the main thread prevents the client from sending heartbeats
2. **Garbage Collection Pauses**: Long GC pauses in Python can cause missed heartbeats
3. **Blocking I/O**: Synchronous I/O operations that block the event loop
4. **Docker Resource Constraints**: CPU/memory limits causing pauses in containerized environments
5. **Network Issues**: Packet loss or high latency

## Solution

The fix increases the heartbeat interval from the pika default (60s) to 300s (5 minutes) and adds a `blocked_connection_timeout` of 600s (10 minutes). This provides more tolerance for CPU-intensive workloads while maintaining connection health detection.

### Configuration Parameters

Both `RabbitMQPublisher` and `RabbitMQSubscriber` now support:

- **`heartbeat`** (default: 300 seconds)
  - Interval between heartbeat frames sent by the client
  - Higher values reduce network overhead and prevent disconnects during CPU-intensive tasks
  - Set to 0 to disable (not recommended for production)
  
- **`blocked_connection_timeout`** (default: 600 seconds)
  - Timeout for connections blocked due to TCP backpressure
  - Should be at least 2x the heartbeat interval
  - Prevents indefinite hangs when the broker is flow-controlled

### Environment Variables

You can override the defaults using environment variables:

```bash
export RABBITMQ_HEARTBEAT=450               # Set heartbeat to 7.5 minutes
export RABBITMQ_BLOCKED_CONNECTION_TIMEOUT=900  # Set timeout to 15 minutes
```

### Programmatic Configuration

```python
from copilot_message_bus.rabbitmq_publisher import RabbitMQPublisher

publisher = RabbitMQPublisher(
    host="messagebus",
    port=5672,
    username="guest",
    password="guest",
    heartbeat=300,  # 5 minutes
    blocked_connection_timeout=600,  # 10 minutes
)
```

### Configuration via DriverConfig

```python
from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_Rabbitmq

config = DriverConfig_MessageBus_Rabbitmq(
    rabbitmq_host="messagebus",
    rabbitmq_port=5672,
    rabbitmq_username="guest",
    rabbitmq_password="guest",
    heartbeat=300,
    blocked_connection_timeout=600,
)

publisher = RabbitMQPublisher.from_config(config)
```

## Troubleshooting

### Identifying Heartbeat Timeouts

1. **Check RabbitMQ logs**:
   ```bash
   docker logs messagebus 2>&1 | grep "missed heartbeats"
   ```

2. **Check which connections are timing out**:
   ```bash
   docker exec messagebus rabbitmqctl list_connections name peer_host timeout
   ```

3. **Monitor connection state**:
   ```bash
   docker exec messagebus rabbitmqctl list_connections state | sort | uniq -c
   ```

### Debugging High Load Scenarios

If heartbeat timeouts occur during high load:

1. **Monitor service CPU/memory**:
   ```bash
   docker stats --no-stream
   ```

2. **Check for long-running tasks**:
   - Review service logs for slow operations
   - Look for GC pauses in Python services
   - Check for blocking I/O operations

3. **Increase heartbeat interval**:
   - For CPU-intensive services (parsing, summarization), consider 450-600s
   - Balance between detection speed and tolerance

### Best Practices

1. **Match heartbeat to workload**:
   - Lightweight services: 60-120s
   - Standard processing: 300s (default)
   - CPU-intensive: 450-600s
   - Real-time/interactive: 30-60s

2. **Set blocked_connection_timeout >= 2x heartbeat**:
   - Ensures timeout detection before heartbeat failure
   - Prevents false positives during temporary TCP backpressure

3. **Monitor metrics**:
   - RabbitMQ connection count
   - Connection churn rate
   - Queue message rates
   - Service processing times

4. **Resource allocation**:
   - Ensure Docker containers have adequate CPU/memory
   - Avoid CPU throttling (use CPU shares, not limits)
   - Monitor for memory pressure causing swapping

## Validation

To verify the fix is working:

1. **Check connection parameters**:
   ```bash
   docker exec messagebus rabbitmqctl list_connections timeout | grep -v "^timeout"
   ```
   Should show 300 (seconds) for services using the updated clients.

2. **Run load tests**:
   ```bash
   # Ingest test data and monitor for connection drops
   docker logs messagebus -f | grep -i "connection\|heartbeat"
   ```

3. **Monitor Grafana dashboards**:
   - RabbitMQ connections panel
   - Service health metrics
   - Message processing rates

## References

- [RabbitMQ Heartbeats Documentation](https://www.rabbitmq.com/heartbeats.html)
- [pika Connection Parameters](https://pika.readthedocs.io/en/stable/modules/parameters.html)
- [Issue: Investigate RabbitMQ heartbeat timeouts](https://github.com/Alan-Jowett/CoPilot-For-Consensus)
