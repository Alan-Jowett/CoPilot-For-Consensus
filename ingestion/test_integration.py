#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Integration test script to verify ingestion service can:
1. Connect to RabbitMQ messagebus
2. Push metrics to Prometheus
3. Publish events when ingesting archives
"""

import sys
import time
import requests
import pika

def test_rabbitmq_connection():
    """Test connection to RabbitMQ."""
    print("\n=== Testing RabbitMQ Connection ===")
    try:
        # Connect to RabbitMQ
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=2
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Declare exchange (this is what copilot_events uses)
        channel.exchange_declare(exchange='copilot.events', exchange_type='topic', durable=True)

        # Create a test queue to listen for events
        result = channel.queue_declare(queue='test_ingestion_events', exclusive=False)
        queue_name = result.method.queue

        # Bind to archive ingestion events
        channel.queue_bind(exchange='copilot.events', queue=queue_name, routing_key='archive.ingested')
        channel.queue_bind(exchange='copilot.events', queue=queue_name, routing_key='archive.ingestion.failed')

        print(f"✅ Successfully connected to RabbitMQ")
        print(f"   Queue: {queue_name}")
        print(f"   Listening for: archive.ingested, archive.ingestion.failed")

        connection.close()
        return True

    except Exception as e:
        print(f"❌ Failed to connect to RabbitMQ: {e}")
        return False


def test_prometheus_connection():
    """Test connection to Prometheus."""
    print("\n=== Testing Prometheus Connection ===")
    try:
        response = requests.get('http://localhost:9090/api/v1/status/config', timeout=5)
        if response.status_code == 200:
            print("✅ Successfully connected to Prometheus")
            print(f"   Endpoint: http://localhost:9090")
            return True
        else:
            print(f"❌ Prometheus returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to Prometheus: {e}")
        return False


def check_rabbitmq_management():
    """Check RabbitMQ management interface for queues and messages."""
    print("\n=== Checking RabbitMQ Management Interface ===")
    try:
        response = requests.get('http://localhost:15672/api/queues', auth=('guest', 'guest'), timeout=5)
        if response.status_code == 200:
            queues = response.json()
            print(f"✅ RabbitMQ Management API accessible")
            print(f"   Total queues: {len(queues)}")

            # Look for copilot-related queues
            copilot_queues = [q for q in queues if 'copilot' in q.get('name', '').lower() or 'archive' in q.get('name', '').lower()]
            if copilot_queues:
                print(f"   Copilot queues found: {len(copilot_queues)}")
                for q in copilot_queues:
                    print(f"     - {q['name']}: {q.get('messages', 0)} messages")
            return True
        else:
            print(f"❌ Management API returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to access RabbitMQ Management: {e}")
        return False


def monitor_events(duration_seconds=30):
    """Monitor RabbitMQ for ingestion events."""
    print(f"\n=== Monitoring for Events ({duration_seconds}s) ===")
    print("Run the ingestion service now in another terminal:")
    print("  docker compose run --rm ingestion")
    print("\nListening for events...")

    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Declare exchange and queue
        channel.exchange_declare(exchange='copilot.events', exchange_type='topic', durable=True)
        result = channel.queue_declare(queue='test_monitor', exclusive=True)
        queue_name = result.method.queue

        # Bind to all archive events
        channel.queue_bind(exchange='copilot.events', queue=queue_name, routing_key='archive.*')
        channel.queue_bind(exchange='copilot.events', queue=queue_name, routing_key='archive.ingestion.*')

        events_received = []

        def callback(ch, method, properties, body):
            timestamp = time.strftime('%H:%M:%S')
            print(f"\n[{timestamp}] 📨 Event received!")
            print(f"  Routing key: {method.routing_key}")
            print(f"  Body: {body.decode('utf-8')[:200]}...")
            events_received.append({
                'routing_key': method.routing_key,
                'body': body.decode('utf-8'),
                'timestamp': timestamp
            })

        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

        # Start consuming with a timeout
        print(f"\n👂 Listening on queue '{queue_name}'...")
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            connection.process_data_events(time_limit=1)

        connection.close()

        print(f"\n=== Monitoring Complete ===")
        print(f"Total events received: {len(events_received)}")

        if events_received:
            print("\n✅ Events were successfully received from ingestion service!")
            for i, event in enumerate(events_received, 1):
                print(f"\n  Event {i}:")
                print(f"    Routing key: {event['routing_key']}")
                print(f"    Timestamp: {event['timestamp']}")
        else:
            print("\n⚠️  No events received. Make sure to run the ingestion service.")

        return len(events_received) > 0

    except Exception as e:
        print(f"\n❌ Error monitoring events: {e}")
        return False


def main():
    """Run integration tests."""
    print("=" * 60)
    print("Ingestion Service Integration Test")
    print("=" * 60)

    # Check prerequisites
    rabbitmq_ok = test_rabbitmq_connection()
    prometheus_ok = test_prometheus_connection()
    management_ok = check_rabbitmq_management()

    if not (rabbitmq_ok and prometheus_ok and management_ok):
        print("\n❌ Prerequisites not met. Ensure RabbitMQ, RabbitMQ Management, and Prometheus are running:")
        print("   docker compose up -d messagebus monitoring")
        print("   RabbitMQ Management UI: http://localhost:15672 (guest/guest)")
        sys.exit(1)

    print("\n✅ All prerequisites met!")

    # Prompt to run ingestion
    print("\n" + "=" * 60)
    print("Ready to test ingestion service")
    print("=" * 60)

    choice = input("\nStart monitoring for events? (y/n): ").lower()
    if choice == 'y':
        monitor_events(duration_seconds=60)
    else:
        print("\nTo manually test, run:")
        print("  docker compose run --rm ingestion")
        print("\nThen check RabbitMQ Management UI:")
        print("  http://localhost:15672 (guest/guest)")


if __name__ == "__main__":
    # Check if pika is installed
    try:
        import pika
        import requests
    except ImportError:
        print("Required packages not found.")
        print("Please install the required packages by running:")
        print(f"  {sys.executable} -m pip install pika requests")
        sys.exit(1)

    main()
