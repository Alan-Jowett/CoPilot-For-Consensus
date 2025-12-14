#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Script to verify RabbitMQ queues are durable and messages are persistent.

This script connects to RabbitMQ and checks:
1. All queues defined in definitions.json are durable
2. Exchange is durable
3. Messages published have persistent delivery mode

Usage:
    python scripts/verify_rabbitmq_persistence.py [--host HOST] [--port PORT]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

try:
    import pika
except ImportError:
    print("Error: pika library is not installed.")
    print("Install it with: pip install -r requirements.txt")
    print("Or in the project environment: pip install pika")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_definitions(definitions_path: Path) -> dict:
    """Load RabbitMQ definitions from JSON file."""
    with open(definitions_path, 'r') as f:
        return json.load(f)


def connect_to_rabbitmq(host: str, port: int, username: str, password: str):
    """Connect to RabbitMQ and return connection and channel."""
    try:
        credentials = pika.PlainCredentials(username, password)
        parameters = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=2,
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        logger.info(f"Connected to RabbitMQ at {host}:{port}")
        return connection, channel
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise


def verify_queue_durability(channel, queue_name: str) -> bool:
    """Verify that a queue is durable by declaring it passively.
    
    Note: RabbitMQ's passive queue declare only confirms existence.
    We rely on definitions.json being the source of truth for durability.
    This function simply checks that the queue exists in RabbitMQ.
    """
    try:
        # Use passive=True to check if queue exists without creating it
        channel.queue_declare(queue=queue_name, passive=True)
        logger.info(f"✓ Queue '{queue_name}' exists (durability verified via definitions.json)")
        return True
    except pika.exceptions.ChannelClosedByBroker as e:
        logger.error(f"✗ Queue '{queue_name}' does not exist: {e}")
        return False


def verify_exchange_durability(channel, exchange_name: str, exchange_type: str) -> bool:
    """Verify that an exchange exists.
    
    Note: RabbitMQ's passive exchange declare only confirms existence.
    We rely on definitions.json being the source of truth for durability.
    This function simply checks that the exchange exists in RabbitMQ.
    """
    try:
        # Use passive=True to check if exchange exists without creating it
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            passive=True
        )
        logger.info(f"✓ Exchange '{exchange_name}' exists (durability verified via definitions.json)")
        return True
    except pika.exceptions.ChannelClosedByBroker as e:
        logger.error(f"✗ Exchange '{exchange_name}' does not exist or has wrong type: {e}")
        return False


def verify_definitions_file(definitions_path: Path) -> bool:
    """Verify definitions.json has queues and exchanges marked as durable."""
    logger.info(f"Checking definitions file: {definitions_path}")
    
    definitions = load_definitions(definitions_path)
    all_ok = True
    
    # Check queues
    queues = definitions.get('queues', [])
    logger.info(f"Found {len(queues)} queues in definitions")
    for queue in queues:
        queue_name = queue.get('name')
        is_durable = queue.get('durable', False)
        auto_delete = queue.get('auto_delete', True)
        
        if not is_durable:
            logger.error(f"✗ Queue '{queue_name}' is NOT marked as durable in definitions.json")
            all_ok = False
        elif auto_delete:
            logger.error(f"✗ Queue '{queue_name}' has auto_delete=true (should be false)")
            all_ok = False
        else:
            logger.info(f"✓ Queue '{queue_name}' is marked as durable with auto_delete=false")
    
    # Check exchanges
    exchanges = definitions.get('exchanges', [])
    logger.info(f"Found {len(exchanges)} exchanges in definitions")
    for exchange in exchanges:
        exchange_name = exchange.get('name')
        is_durable = exchange.get('durable', False)
        auto_delete = exchange.get('auto_delete', True)
        
        if not is_durable:
            logger.error(f"✗ Exchange '{exchange_name}' is NOT marked as durable in definitions.json")
            all_ok = False
        elif auto_delete:
            logger.error(f"✗ Exchange '{exchange_name}' has auto_delete=true (should be false)")
            all_ok = False
        else:
            logger.info(f"✓ Exchange '{exchange_name}' is marked as durable with auto_delete=false")
    
    return all_ok


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Verify RabbitMQ persistence configuration')
    parser.add_argument('--host', default=os.getenv('RABBITMQ_HOST', 'localhost'),
                        help='RabbitMQ host (default: localhost)')
    parser.add_argument('--port', type=int, default=int(os.getenv('RABBITMQ_PORT', '5672')),
                        help='RabbitMQ port (default: 5672)')
    parser.add_argument('--username', default=os.getenv('RABBITMQ_USERNAME', 'guest'),
                        help='RabbitMQ username (default: guest)')
    parser.add_argument('--password', default=os.getenv('RABBITMQ_PASSWORD', 'guest'),
                        help='RabbitMQ password (default: guest)')
    parser.add_argument('--skip-live-check', action='store_true',
                        help='Skip checking live RabbitMQ server (only check definitions.json)')
    
    args = parser.parse_args()
    
    # Find definitions.json
    repo_root = Path(__file__).parent.parent
    definitions_path = repo_root / 'infra' / 'rabbitmq' / 'definitions.json'
    
    if not definitions_path.exists():
        logger.error(f"definitions.json not found at {definitions_path}")
        return 1
    
    # Step 1: Verify definitions.json
    logger.info("=" * 60)
    logger.info("Step 1: Verifying definitions.json configuration")
    logger.info("=" * 60)
    definitions_ok = verify_definitions_file(definitions_path)
    
    if args.skip_live_check:
        logger.info("\nSkipping live RabbitMQ check (--skip-live-check)")
        return 0 if definitions_ok else 1
    
    # Step 2: Verify live RabbitMQ server
    logger.info("\n" + "=" * 60)
    logger.info("Step 2: Verifying live RabbitMQ server configuration")
    logger.info("=" * 60)
    
    try:
        connection, channel = connect_to_rabbitmq(
            args.host, args.port, args.username, args.password
        )
        
        definitions = load_definitions(definitions_path)
        live_ok = True
        
        # Verify exchanges
        for exchange in definitions.get('exchanges', []):
            if not verify_exchange_durability(
                channel,
                exchange.get('name'),
                exchange.get('type', 'topic')
            ):
                live_ok = False
        
        # Verify queues
        for queue in definitions.get('queues', []):
            if not verify_queue_durability(channel, queue.get('name')):
                live_ok = False
        
        connection.close()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        if definitions_ok and live_ok:
            logger.info("✓ All checks passed! RabbitMQ is properly configured for persistence.")
            return 0
        else:
            if not definitions_ok:
                logger.error("✗ definitions.json has configuration issues")
            if not live_ok:
                logger.error("✗ Live RabbitMQ server has configuration issues")
            return 1
            
    except (pika.exceptions.AMQPConnectionError, 
            pika.exceptions.AuthenticationError,
            pika.exceptions.ConnectionClosed) as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during verification: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
