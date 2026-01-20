# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Peek Azure Service Bus dead-letter messages for a topic subscription.

This script is intended for diagnostics (does not consume/complete messages).

Usage (PowerShell):
    # Connection string auth
    $env:AZURE_SERVICEBUS_CONNECTION_STRING = "..."
    python scripts/peek_servicebus_dlq.py --topic copilot.events --subscription parsing --max 10

    # Azure AD auth (for namespaces with disableLocalAuth=true)
    $env:AZURE_SERVICEBUS_NAMESPACE = "your-namespace.servicebus.windows.net"
    python scripts/peek_servicebus_dlq.py --auth aad --topic copilot.events --subscription parsing --max 10

Notes:
- Uses AMQP-over-WebSockets when available to avoid blocked AMQP ports.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any

from azure.servicebus import ServiceBusClient, ServiceBusSubQueue

try:
    from azure.identity import AzureCliCredential, DefaultAzureCredential
except ImportError:  # pragma: no cover
    DefaultAzureCredential = None  # type: ignore
    AzureCliCredential = None  # type: ignore

try:
    from azure.servicebus import TransportType
except ImportError:  # pragma: no cover
    TransportType = None  # type: ignore


def _body_preview(msg: Any, limit: int = 800) -> str:
    try:
        body_bytes = b"".join(b for b in msg.body)
        text = body_bytes.decode("utf-8", errors="replace")
        return text[:limit]
    except Exception:
        return "<unavailable>"


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Peek Service Bus DLQ messages")
    parser.add_argument(
        "--auth",
        choices=("auto", "connection-string", "aad"),
        default="auto",
        help=(
            "Authentication method. Use 'aad' when the namespace has disableLocalAuth=true. "
            "'auto' prefers connection string if present."
        ),
    )
    parser.add_argument(
        "--fully-qualified-namespace",
        help=(
            "Service Bus namespace host, e.g. copilot-sb-dev-xyz.servicebus.windows.net. "
            "Used for Azure AD auth."
        ),
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--max", type=int, default=10)
    args = parser.parse_args()

    conn = os.environ.get("SERVICEBUS_CONNECTION_STRING") or os.environ.get(
        "AZURE_SERVICEBUS_CONNECTION_STRING"
    )
    fqn = (
        args.fully_qualified_namespace
        or os.environ.get("SERVICEBUS_FULLY_QUALIFIED_NAMESPACE")
        or os.environ.get("AZURE_SERVICEBUS_NAMESPACE")
    )

    kwargs: dict[str, Any] = {}
    if TransportType is not None:
        kwargs["transport_type"] = TransportType.AmqpOverWebsocket

    use_aad = False
    if args.auth == "aad":
        use_aad = True
    elif args.auth == "connection-string":
        use_aad = False
    else:
        # auto
        use_aad = not bool(conn)

    if use_aad:
        if DefaultAzureCredential is None:
            raise SystemExit("azure-identity is required for AAD auth")
        if not fqn:
            raise SystemExit(
                "Missing --fully-qualified-namespace (or SERVICEBUS_FULLY_QUALIFIED_NAMESPACE) for AAD auth"
            )
        if AzureCliCredential is not None:
            credential = AzureCliCredential()
        else:
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        client = ServiceBusClient(
            fully_qualified_namespace=fqn,
            credential=credential,
            retry_total=1,
            **kwargs,
        )
        print("Auth: AAD")
    else:
        if not conn:
            raise SystemExit(
                "Missing connection string env var: set SERVICEBUS_CONNECTION_STRING or AZURE_SERVICEBUS_CONNECTION_STRING"
            )
        client = ServiceBusClient.from_connection_string(conn, retry_total=1, **kwargs)
        print("Auth: connection-string")

    print(f"Using websocket transport: {bool(kwargs)}")
    print(f"Topic: {args.topic}")
    print(f"Subscription: {args.subscription}")

    with client:
        with client.get_subscription_receiver(
            topic_name=args.topic,
            subscription_name=args.subscription,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
        ) as receiver:
            msgs: list[Any] = []
            seen: set[tuple[Any, Any]] = set()
            while len(msgs) < args.max:
                batch_size = min(50, args.max - len(msgs))
                batch = receiver.peek_messages(max_message_count=batch_size)
                if not batch:
                    break
                new = 0
                for m in batch:
                    key = (getattr(m, "sequence_number", None), getattr(m, "message_id", None))
                    if key in seen:
                        continue
                    seen.add(key)
                    msgs.append(m)
                    new += 1
                    if len(msgs) >= args.max:
                        break
                if new == 0:
                    break

            print(f"Peeked {len(msgs)} DLQ messages")
            for i, m in enumerate(msgs, 1):
                reason = getattr(m, "dead_letter_reason", None)
                desc = getattr(m, "dead_letter_error_description", None)

                mid = getattr(m, "message_id", None)
                corr = getattr(m, "correlation_id", None)
                subj = getattr(m, "subject", None)
                seq = getattr(m, "sequence_number", None)
                enq = _to_iso(getattr(m, "enqueued_time_utc", None))

                body = _body_preview(m)
                event_type = None
                event_id = None
                if body.lstrip().startswith("{"):
                    try:
                        parsed = json.loads(body)
                    except json.JSONDecodeError:
                        # Best-effort JSON parsing: if the body is not valid JSON, just
                        # ignore the error and continue printing the raw body preview.
                        parsed = None

                    if isinstance(parsed, dict):
                        event_type = parsed.get("event_type")
                        event_id = parsed.get("event_id")

                print(f"\n[{i}] sequence_number={seq} message_id={mid} subject={subj} correlation_id={corr}")
                if enq:
                    print(f"    enqueued: {enq}")
                print(f"    dead_letter_reason: {reason}")
                print(f"    dead_letter_error_description: {desc}")
                if event_type or event_id:
                    print(f"    event: {event_type} {event_id}")
                print(f"    body_preview: {body.replace(chr(10), ' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
