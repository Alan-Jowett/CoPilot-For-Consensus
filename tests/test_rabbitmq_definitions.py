# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test RabbitMQ definitions file for completeness.

This test validates that all routing keys used in service code have
corresponding queue declarations and bindings in the RabbitMQ definitions file.
This prevents "unroutable message" errors in production.
"""

import json
import re
from pathlib import Path


def test_rabbitmq_definitions_completeness():
    """Verify all routing keys used in services have corresponding queues and bindings."""
    
    # Load RabbitMQ definitions
    repo_root = Path(__file__).parent.parent
    definitions_path = repo_root / "infra" / "rabbitmq" / "definitions.json"
    
    with open(definitions_path) as f:
        definitions = json.load(f)
    
    # Extract queue names from definitions
    defined_queues = {q["name"] for q in definitions.get("queues", [])}
    
    # Extract routing keys from bindings
    bound_routing_keys = {
        b["routing_key"]
        for b in definitions.get("bindings", [])
        if b.get("source") == "copilot.events"
    }
    
    # Find all routing keys used in service code
    used_routing_keys = set()
    service_dirs = ["ingestion", "parsing", "chunking", "embedding", "orchestrator", "summarization", "reporting"]
    
    for service_dir in service_dirs:
        service_path = repo_root / service_dir / "app"
        if not service_path.exists():
            continue
        
        for py_file in service_path.glob("*.py"):
            content = py_file.read_text()
            
            # Find all routing_key parameters in publish/subscribe calls
            # Pattern: routing_key="some.key" or routing_key='some.key'
            # Use [^"']+ to match any non-quote characters (handles hyphens, etc.)
            matches = re.findall(r'routing_key=["\']([-\w.]+)["\']', content)
            used_routing_keys.update(matches)
    
    # Check that all used routing keys have corresponding queues
    missing_queues = used_routing_keys - defined_queues
    assert not missing_queues, (
        f"Routing keys used in services but missing queue declarations: {missing_queues}\n"
        f"Add these queues to infra/rabbitmq/definitions.json"
    )
    
    # Check that all used routing keys have bindings
    missing_bindings = used_routing_keys - bound_routing_keys
    assert not missing_bindings, (
        f"Routing keys used in services but missing bindings: {missing_bindings}\n"
        f"Add bindings for these routing keys to infra/rabbitmq/definitions.json"
    )
    
    # Check that all queues have bindings (no orphaned queues)
    # Extract the destination queues from bindings
    bound_queue_names = {
        b["destination"]
        for b in definitions.get("bindings", [])
        if b.get("source") == "copilot.events" and b.get("destination_type") == "queue"
    }
    orphaned_queues = defined_queues - bound_queue_names
    # Note: This is a warning, not a failure, as some queues might be intentionally unbound
    if orphaned_queues:
        print(f"Warning: Queues without bindings (might be intentional): {orphaned_queues}")
    
    print(f"✓ All {len(used_routing_keys)} routing keys have queue declarations and bindings")
    print(f"✓ Routing keys validated: {sorted(used_routing_keys)}")


def test_rabbitmq_definitions_structure():
    """Verify RabbitMQ definitions file has correct structure."""
    
    repo_root = Path(__file__).parent.parent
    definitions_path = repo_root / "infra" / "rabbitmq" / "definitions.json"
    
    with open(definitions_path) as f:
        definitions = json.load(f)
    
    # Check required top-level keys
    required_keys = ["queues", "exchanges", "bindings"]
    for key in required_keys:
        assert key in definitions, f"Missing required key: {key}"
    
    # Check exchange configuration
    exchanges = definitions["exchanges"]
    assert len(exchanges) >= 1, "At least one exchange should be defined"
    
    # Find the copilot.events exchange
    copilot_exchange = None
    for ex in exchanges:
        if ex.get("name") == "copilot.events":
            copilot_exchange = ex
            break
    
    assert copilot_exchange is not None, "copilot.events exchange not found"
    assert copilot_exchange["type"] == "topic", "copilot.events should be a topic exchange"
    assert copilot_exchange["durable"] is True, "copilot.events should be durable"
    
    # Check queue configuration
    queues = definitions["queues"]
    for queue in queues:
        assert queue["durable"] is True, f"Queue {queue['name']} should be durable"
        assert queue["auto_delete"] is False, f"Queue {queue['name']} should not auto-delete"
    
    # Check binding configuration
    bindings = definitions["bindings"]
    for binding in bindings:
        assert binding["source"] == "copilot.events", f"Binding should use copilot.events exchange"
        assert binding["destination_type"] == "queue", f"Binding should target a queue"
        
        # Verify the bound queue exists
        queue_name = binding["destination"]
        assert queue_name in {q["name"] for q in queues}, (
            f"Binding references non-existent queue: {queue_name}"
        )
        
        # Verify routing key matches queue name (convention)
        routing_key = binding["routing_key"]
        assert routing_key == queue_name, (
            f"Routing key '{routing_key}' should match queue name '{queue_name}' (convention)"
        )
    
    print(f"✓ RabbitMQ definitions structure is valid")
    print(f"✓ Found {len(queues)} queues, {len(bindings)} bindings")


if __name__ == "__main__":
    test_rabbitmq_definitions_structure()
    test_rabbitmq_definitions_completeness()
    print("\n✅ All RabbitMQ definitions tests passed!")
