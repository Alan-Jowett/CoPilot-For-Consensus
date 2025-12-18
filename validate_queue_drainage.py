#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Validation script to demonstrate queue drainage fix.

This script can be run after the system processes data to verify that
queues properly drain to empty when idle, proving the lingering queue
entries issue has been resolved.

Usage:
    python3 validate_queue_drainage.py
    
Environment Variables:
    RABBITMQ_HOST - RabbitMQ host (default: localhost)
    RABBITMQ_MGMT_PORT - RabbitMQ management port (default: 15672)
    RABBITMQ_USER - RabbitMQ username (default: guest)
    RABBITMQ_PASS - RabbitMQ password (default: guest)
"""

import os
import sys
import time
import requests
from typing import Dict, List


def get_rabbitmq_api_url() -> str:
    """Get RabbitMQ management API URL from environment or use default."""
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = os.getenv("RABBITMQ_MGMT_PORT", "15672")
    
    # Validate host (prevent injection)
    if not host or not isinstance(host, str):
        host = "localhost"
    # Remove any protocol prefix if accidentally included
    host = host.replace("http://", "").replace("https://", "").split("/")[0]
    
    # Validate port is numeric
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            port = "15672"
    except (ValueError, TypeError):
        port = "15672"
    
    return f"http://{host}:{port}/api"


def get_rabbitmq_credentials() -> tuple:
    """Get RabbitMQ credentials from environment or use defaults."""
    username = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASS", "guest")
    return (username, password)


def get_queue_stats() -> List[Dict]:
    """Fetch queue statistics from RabbitMQ management API."""
    api_url = get_rabbitmq_api_url()
    auth = get_rabbitmq_credentials()
    
    try:
        response = requests.get(f"{api_url}/queues", auth=auth, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Cannot connect to RabbitMQ management API: {type(e).__name__}")
        print(f"   Check that RabbitMQ is running and accessible")
        sys.exit(1)


def check_for_duplicate_queues(queues: List[Dict]) -> bool:
    """Check if duplicate queues exist that should have been removed."""
    queue_names = {q["name"] for q in queues}
    
    # Queues that should NOT exist (removed from definitions.json)
    forbidden_queues = {
        "chunks.prepared",
        "embeddings.generated",
        "report.published",
        "archive.ingestion.failed",
        "parsing.failed",
        "chunking.failed",
        "embedding.generation.failed",
        "orchestration.failed",
        "summarization.failed",
        "report.delivery.failed",
    }
    
    found_forbidden = queue_names & forbidden_queues
    
    if found_forbidden:
        print("❌ Found duplicate queues that should have been removed:")
        for queue_name in sorted(found_forbidden):
            print(f"   - {queue_name}")
        print("\n   These queues have no consumers and will accumulate messages.")
        print("   They should be removed from infra/rabbitmq/definitions.json")
        return False
    else:
        print("✓ No duplicate queues found")
        return True


def check_queue_drainage(queues: List[Dict]) -> bool:
    """Check if all queues have drained to empty."""
    queues_with_messages = []
    
    for queue in queues:
        name = queue.get("name", "unknown")
        ready = queue.get("messages_ready", 0)
        unacked = queue.get("messages_unacknowledged", 0)
        total = queue.get("messages", 0)
        consumers = queue.get("consumers", 0)
        
        if ready > 0 or unacked > 0:
            queues_with_messages.append({
                "name": name,
                "ready": ready,
                "unacked": unacked,
                "total": total,
                "consumers": consumers,
            })
    
    if queues_with_messages:
        print("⚠️  Queues have lingering messages:")
        for q in queues_with_messages:
            print(f"   - {q['name']}: {q['ready']} ready, {q['unacked']} unacked, "
                  f"{q['total']} total, {q['consumers']} consumers")
        print("\n   This may indicate:")
        print("   - System is still processing")
        print("   - A consumer is not acknowledging messages")
        print("   - A queue has no active consumer")
        return False
    else:
        print("✓ All queues are empty (properly drained)")
        return True


def check_consumer_coverage(queues: List[Dict]) -> bool:
    """Check if all expected queues have active consumers."""
    # Queues that should have consumers (from definitions.json)
    expected_consumers = {
        "archive.ingested": 1,
        "json.parsed": 1,
        "summarization.requested": 1,
        "summary.complete": 1,
    }
    
    missing_consumers = []
    for queue in queues:
        queue_name = queue.get("name")
        if queue_name not in expected_consumers:
            continue
        
        expected_count = expected_consumers[queue_name]
        actual_count = queue.get("consumers", 0)
        
        if actual_count < expected_count:
            missing_consumers.append({
                "name": queue_name,
                "expected": expected_count,
                "actual": actual_count,
            })
    
    if missing_consumers:
        print("⚠️  Queues missing expected consumers:")
        for q in missing_consumers:
            print(f"   - {q['name']}: expected {q['expected']}, found {q['actual']}")
        print("\n   Services may not be running or connected properly.")
        return False
    else:
        print("✓ All queues have active consumers")
        return True


def print_queue_summary(queues: List[Dict]) -> None:
    """Print a summary of all queues."""
    print("\n=== Queue Summary ===")
    print(f"Total queues: {len(queues)}\n")
    
    if not queues:
        print("No queues found.\n")
        return
    
    # Sort by name for consistent output
    sorted_queues = sorted(queues, key=lambda q: q.get("name", ""))
    
    print(f"{'Queue Name':<40} {'Ready':<8} {'Unacked':<8} {'Total':<8} {'Consumers':<10}")
    print("-" * 90)
    
    for queue in sorted_queues:
        name = queue.get("name", "unknown")
        ready = queue.get("messages_ready", 0)
        unacked = queue.get("messages_unacknowledged", 0)
        total = queue.get("messages", 0)
        consumers = queue.get("consumers", 0)
        
        print(f"{name:<40} {ready:<8} {unacked:<8} {total:<8} {consumers:<10}")
    
    print()


def main():
    """Main validation logic."""
    print("=" * 80)
    print("Queue Drainage Validation")
    print("=" * 80)
    print()
    
    # Fetch queue stats
    print("Fetching queue statistics from RabbitMQ...")
    queues = get_queue_stats()
    print(f"Found {len(queues)} queue(s)\n")
    
    # Run validation checks
    all_passed = True
    
    print("--- Check 1: Duplicate Queue Detection ---")
    if not check_for_duplicate_queues(queues):
        all_passed = False
    print()
    
    print("--- Check 2: Consumer Coverage ---")
    if not check_consumer_coverage(queues):
        all_passed = False
    print()
    
    print("--- Check 3: Queue Drainage ---")
    print("Waiting 3 seconds for any in-flight messages to complete...")
    time.sleep(3)
    
    # Refresh stats after wait
    queues = get_queue_stats()
    if not check_queue_drainage(queues):
        all_passed = False
    print()
    
    # Print summary
    print_queue_summary(queues)
    
    # Final result
    print("=" * 80)
    if all_passed:
        print("✅ VALIDATION PASSED - Queues are draining properly")
        print("=" * 80)
        return 0
    else:
        print("⚠️  VALIDATION INCOMPLETE - See warnings above")
        print("=" * 80)
        print("\nNote: Some checks may fail if services are not running or")
        print("      system is still processing. Review warnings carefully.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(130)
