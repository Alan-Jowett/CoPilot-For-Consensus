#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Failed Queue Management Tool

This script provides CLI operations for managing failed message queues in RabbitMQ:
- List all failed queues and their message counts
- Inspect messages in failed queues
- Export messages to JSON for analysis
- Requeue messages back to their original queue for retry
- Purge messages from failed queues

See documents/FAILED_QUEUE_OPERATIONS.md for operational runbook.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from copilot_config import load_driver_config
from copilot_logging import create_logger

try:
    import pika
except ImportError:
    print("Error: pika library not installed. Run: pip install pika", file=sys.stderr)
    sys.exit(1)

logger_config = load_driver_config(
    service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": __name__}
)
logger = create_logger(driver_name="stdout", driver_config=logger_config)


class FailedQueueManager:
    """Manages operations on RabbitMQ failed queues."""

    # Mapping of failed queues to their corresponding success queues
    QUEUE_MAPPINGS = {
        "archive.ingestion.failed": "archive.ingested",
        "parsing.failed": "archive.ingested",
        "chunking.failed": "json.parsed",
        "embedding.generation.failed": "chunks.prepared",
        "summarization.failed": "summarization.requested",
        "orchestration.failed": "archive.ingested",
        "report.delivery.failed": "summary.complete",
    }

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        vhost: str = "/",
    ):
        """Initialize connection to RabbitMQ.

        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            vhost: RabbitMQ virtual host
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.connection = None
        self.channel = None

    def connect(self):
        """Establish connection to RabbitMQ."""
        credentials = pika.PlainCredentials(self.username, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=credentials,
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")

    def disconnect(self):
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    def list_failed_queues(self) -> list[dict[str, Any]]:
        """List all failed queues and their message counts.

        Returns:
            List of dicts with queue name and message count
        """
        queues = []
        for queue_name in self.QUEUE_MAPPINGS.keys():
            try:
                queue_info = self.channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    passive=True,  # Don't create if doesn't exist
                )
                message_count = queue_info.method.message_count
                queues.append(
                    {
                        "queue": queue_name,
                        "message_count": message_count,
                    }
                )
                logger.debug(f"Queue {queue_name}: {message_count} messages")
            except Exception as e:
                logger.warning(f"Failed to get info for queue {queue_name}: {e}")

        return queues

    def inspect_messages(
        self,
        queue_name: str,
        limit: int = 10,
        requeue: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve messages from a queue for inspection.

        Inspection is non-destructive by default - messages are always requeued
        after inspection to preserve queue state.

        Args:
            queue_name: Name of the queue
            limit: Maximum number of messages to retrieve
            requeue: Whether to requeue messages after inspection (default: True)

        Returns:
            List of message dictionaries
        """
        messages = []

        for _ in range(limit):
            # Always use auto_ack=False to ensure messages can be requeued
            method, properties, body = self.channel.basic_get(queue_name, auto_ack=False)

            if method is None:
                # No more messages
                break

            try:
                message_data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                message_data = {"raw_body": body.decode("utf-8", errors="replace")}

            messages.append(
                {
                    "delivery_tag": method.delivery_tag,
                    "exchange": method.exchange,
                    "routing_key": method.routing_key,
                    "redelivered": method.redelivered,
                    "message": message_data,
                    "properties": {
                        "content_type": properties.content_type,
                        "delivery_mode": properties.delivery_mode,
                        "timestamp": properties.timestamp,
                    },
                }
            )

            # Requeue message to preserve queue state (inspection is non-destructive)
            if requeue:
                self.channel.basic_nack(method.delivery_tag, requeue=True)
            else:
                self.channel.basic_ack(method.delivery_tag)

        logger.info(f"Retrieved {len(messages)} messages from {queue_name}")
        return messages

    def export_messages(
        self,
        queue_name: str,
        output_file: str,
        limit: int | None = None,
    ) -> int:
        """Export all messages from a queue to a JSON file.

        Args:
            queue_name: Name of the queue
            output_file: Path to output JSON file
            limit: Maximum messages to export (None = all)

        Returns:
            Number of messages exported
        """
        # Get queue message count
        queue_info = self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            passive=True,
        )
        total_count = queue_info.method.message_count

        if limit is None:
            limit = total_count

        logger.info(f"Exporting up to {limit} messages from {queue_name} (total: {total_count})")

        # Retrieve messages with requeue
        messages = self.inspect_messages(queue_name, limit=limit, requeue=True)

        # Write to file
        export_data = {
            "queue": queue_name,
            "export_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_messages_in_queue": total_count,
            "messages_exported": len(messages),
            "messages": messages,
        }

        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(messages)} messages to {output_file}")
        return len(messages)

    def requeue_messages(
        self,
        queue_name: str,
        target_queue: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> int:
        """Requeue messages from failed queue to target queue.

        Args:
            queue_name: Name of the failed queue
            target_queue: Target queue (defaults to mapped success queue)
            limit: Maximum messages to requeue (None = all)
            dry_run: If True, only simulate without actual requeue

        Returns:
            Number of messages requeued
        """
        if target_queue is None:
            target_queue = self.QUEUE_MAPPINGS.get(queue_name)
            if target_queue is None:
                raise ValueError(f"Unknown failed queue: {queue_name}. Specify --target-queue.")

        # Get queue message count
        queue_info = self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            passive=True,
        )
        total_count = queue_info.method.message_count

        if limit is None:
            limit = total_count

        logger.info(
            f"{'[DRY RUN] ' if dry_run else ''}Requeuing up to {limit} messages from {queue_name} to {target_queue}"
        )

        requeued_count = 0

        for _ in range(limit):
            method, properties, body = self.channel.basic_get(queue_name, auto_ack=False)

            if method is None:
                break

            if not dry_run:
                # Determine routing key from target queue name
                # Most queues use the queue name as routing key (e.g., archive.ingested)
                routing_key = target_queue

                # Publish to target queue
                self.channel.basic_publish(
                    exchange="copilot.events",
                    routing_key=routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type=properties.content_type,
                        delivery_mode=2,  # Persistent
                    ),
                )

                # Acknowledge original message (removes from failed queue)
                self.channel.basic_ack(method.delivery_tag)
            else:
                # In dry-run, requeue to same queue
                self.channel.basic_nack(method.delivery_tag, requeue=True)

            requeued_count += 1

        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Requeued {requeued_count} messages")
        return requeued_count

    def purge_messages(
        self,
        queue_name: str,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> int:
        """Purge messages from a failed queue.

        Args:
            queue_name: Name of the failed queue
            limit: Maximum messages to purge (None = all)
            dry_run: If True, only simulate without actual purge

        Returns:
            Number of messages purged
        """
        if limit is None:
            # Purge entire queue
            if dry_run:
                queue_info = self.channel.queue_declare(
                    queue=queue_name,
                    durable=True,
                    passive=True,
                )
                count = queue_info.method.message_count
                logger.info(f"[DRY RUN] Would purge {count} messages from {queue_name}")
                return count
            else:
                result = self.channel.queue_purge(queue_name)
                logger.info(f"Purged {result.method.message_count} messages from {queue_name}")
                return result.method.message_count
        else:
            # Purge specific number of messages
            purged_count = 0

            for _ in range(limit):
                # Always use auto_ack=False to prevent accidental deletion in dry-run
                method, _, _ = self.channel.basic_get(queue_name, auto_ack=False)

                if method is None:
                    break

                if dry_run:
                    # Requeue in dry-run (don't actually purge)
                    self.channel.basic_nack(method.delivery_tag, requeue=True)
                else:
                    # Actually delete the message
                    self.channel.basic_ack(method.delivery_tag)

                purged_count += 1

            logger.info(f"{'[DRY RUN] ' if dry_run else ''}Purged {purged_count} messages from {queue_name}")
            return purged_count


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage failed message queues in RabbitMQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all failed queues
  %(prog)s list

  # Inspect first 10 messages in parsing.failed
  %(prog)s inspect parsing.failed --limit 10

  # Export messages for analysis
  %(prog)s export parsing.failed --output backup.json

  # Requeue messages (dry-run first)
  %(prog)s requeue parsing.failed --dry-run
  %(prog)s requeue parsing.failed

  # Purge old messages
  %(prog)s purge parsing.failed --limit 100 --dry-run

For full operational guide, see documents/FAILED_QUEUE_OPERATIONS.md
        """,
    )

    # Connection options
    parser.add_argument(
        "--rabbitmq-host",
        default=os.getenv("MESSAGE_BUS_HOST", "localhost"),
        help="RabbitMQ host (default: localhost or $MESSAGE_BUS_HOST)",
    )
    parser.add_argument(
        "--rabbitmq-port",
        type=int,
        default=int(os.getenv("MESSAGE_BUS_PORT", "5672")),
        help="RabbitMQ port (default: 5672 or $MESSAGE_BUS_PORT)",
    )
    parser.add_argument(
        "--rabbitmq-user",
        default=os.getenv("MESSAGE_BUS_USER", "guest"),
        help="RabbitMQ username (default: guest or $MESSAGE_BUS_USER)",
    )
    parser.add_argument(
        "--rabbitmq-password",
        default=os.getenv("MESSAGE_BUS_PASSWORD", "guest"),
        help="RabbitMQ password (default: guest or $MESSAGE_BUS_PASSWORD)",
    )
    parser.add_argument(
        "--rabbitmq-vhost",
        default=os.getenv("MESSAGE_BUS_VHOST", "/"),
        help="RabbitMQ vhost (default: / or $MESSAGE_BUS_VHOST)",
    )

    # Logging
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    subparsers.add_parser("list", help="List all failed queues and message counts")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect messages in a queue")
    inspect_parser.add_argument("queue", help="Queue name (e.g., parsing.failed)")
    inspect_parser.add_argument("--limit", type=int, default=10, help="Max messages to retrieve (default: 10)")
    inspect_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export messages to JSON file")
    export_parser.add_argument("queue", help="Queue name (e.g., parsing.failed)")
    export_parser.add_argument("--output", required=True, help="Output JSON file path")
    export_parser.add_argument("--limit", type=int, help="Max messages to export (default: all)")

    # Requeue command
    requeue_parser = subparsers.add_parser("requeue", help="Requeue messages to original queue")
    requeue_parser.add_argument("queue", help="Failed queue name (e.g., parsing.failed)")
    requeue_parser.add_argument("--target-queue", help="Target queue (default: auto-mapped)")
    requeue_parser.add_argument("--limit", type=int, help="Max messages to requeue (default: all)")
    requeue_parser.add_argument("--dry-run", action="store_true", help="Simulate without actual requeue")

    # Purge command
    purge_parser = subparsers.add_parser("purge", help="Purge messages from queue")
    purge_parser.add_argument("queue", help="Failed queue name (e.g., parsing.failed)")
    purge_parser.add_argument("--limit", type=int, help="Max messages to purge (default: all)")
    purge_parser.add_argument("--dry-run", action="store_true", help="Simulate without actual purge")
    purge_parser.add_argument("--confirm", action="store_true", help="Confirm purge operation (required)")

    args = parser.parse_args()

    # Configure logging
    global logger
    if args.verbose:
        logger_config = load_driver_config(
            service=None, adapter="logger", driver="stdout", fields={"level": "DEBUG", "name": __name__}
        )
        logger = create_logger(driver_name="stdout", driver_config=logger_config)

    # Create manager
    manager = FailedQueueManager(
        host=args.rabbitmq_host,
        port=args.rabbitmq_port,
        username=args.rabbitmq_user,
        password=args.rabbitmq_password,
        vhost=args.rabbitmq_vhost,
    )

    try:
        manager.connect()

        # Execute command
        if args.command == "list":
            queues = manager.list_failed_queues()
            print(json.dumps(queues, indent=2))

            # Summary
            total_messages = sum(q["message_count"] for q in queues)
            print(f"\nTotal failed messages across all queues: {total_messages}", file=sys.stderr)

        elif args.command == "inspect":
            messages = manager.inspect_messages(
                args.queue,
                limit=args.limit,
                requeue=True,  # Requeue after inspection
            )

            if args.pretty:
                print(json.dumps(messages, indent=2))
            else:
                for msg in messages:
                    print(json.dumps(msg))

        elif args.command == "export":
            count = manager.export_messages(
                args.queue,
                args.output,
                limit=args.limit,
            )
            print(f"Exported {count} messages to {args.output}", file=sys.stderr)

        elif args.command == "requeue":
            count = manager.requeue_messages(
                args.queue,
                target_queue=args.target_queue,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            status = "[DRY RUN] Would requeue" if args.dry_run else "Requeued"
            print(f"{status} {count} messages from {args.queue}", file=sys.stderr)

        elif args.command == "purge":
            if not args.dry_run and not args.confirm:
                print("ERROR: Purge requires --confirm flag (or use --dry-run to test)", file=sys.stderr)
                sys.exit(1)

            count = manager.purge_messages(
                args.queue,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            status = "[DRY RUN] Would purge" if args.dry_run else "Purged"
            print(f"{status} {count} messages from {args.queue}", file=sys.stderr)

    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=args.verbose)
        sys.exit(1)
    finally:
        manager.disconnect()


if __name__ == "__main__":
    main()
