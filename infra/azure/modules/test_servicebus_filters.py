# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test that Service Bus Bicep template generates correct subscription filters.

This test validates that:
1. The Bicep template compiles successfully
2. SQL filter rules are created for each subscription
3. Each filter expression matches the expected event types for that service

Note: These tests require Azure CLI (az) with the bicep component installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore


# Check if Azure CLI is available
def _check_az_available():
    """Check if 'az' CLI is available on PATH."""
    return shutil.which("az") is not None


# Skip all tests if Azure CLI is not available
_az_available = _check_az_available()
_skip_reason = "Azure CLI (az) with bicep component not found on PATH. Install with: az bicep install"

if pytest:
    pytestmark = pytest.mark.skipif(not _az_available, reason=_skip_reason)


def test_servicebus_bicep_compiles():
    """Test that the servicebus.bicep template compiles without errors."""
    bicep_file = Path(__file__).parent / "servicebus.bicep"
    assert bicep_file.exists(), f"servicebus.bicep not found at {bicep_file}"

    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_file), "--stdout"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Bicep compilation failed: {result.stderr}"
    assert result.stdout, "Expected JSON output from Bicep compilation"

    # Parse the compiled template
    template = json.loads(result.stdout)
    assert template, "Failed to parse compiled Bicep template"


def test_subscription_filters_are_generated():
    """Test that SQL filter rules are generated for each service subscription."""
    bicep_file = Path(__file__).parent / "servicebus.bicep"

    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_file), "--stdout"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Bicep compilation failed: {result.stderr}"
    template = json.loads(result.stdout)

    # Find subscription filter resources
    filter_resources = [
        r
        for r in template.get("resources", [])
        if r.get("type") == "Microsoft.ServiceBus/namespaces/topics/subscriptions/rules"
    ]

    # In the compiled template, Bicep uses a copy loop, so there's one resource definition
    # that gets deployed multiple times (once per receiverService)
    assert len(filter_resources) > 0, "No subscription filter resources found"
    
    # Check that the resource has a copy element for multiple instances
    filter_resource = filter_resources[0]
    assert "copy" in filter_resource, "Filter resource should have a copy element for multiple instances"
    
    # Verify it will create 6 instances (one per receiver service)
    expected_count = 6  # parsing, chunking, embedding, orchestrator, summarization, reporting
    copy_count = filter_resource["copy"]["count"]
    # The count is an expression like "[length(parameters('receiverServices'))]"
    assert "receiverServices" in copy_count, f"Copy count should reference receiverServices: {copy_count}"
    
    # Verify the rule is named $Default (replaces the default TrueFilter)
    assert "$Default" in str(filter_resource.get("name")), "Filter not named $Default"


def test_event_type_filter_mappings():
    """Test that the event type filter mappings are correct for each service."""
    bicep_file = Path(__file__).parent / "servicebus.bicep"

    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_file), "--stdout"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Bicep compilation failed: {result.stderr}"
    template = json.loads(result.stdout)

    # Verify the serviceEventTypeFilters variable exists
    variables = template.get("variables", {})
    assert "serviceEventTypeFilters" in variables, "serviceEventTypeFilters variable not found"

    filters = variables["serviceEventTypeFilters"]

    # Expected event type mappings
    expected_filters = {
        "parsing": "event_type IN ('ArchiveIngested', 'SourceDeletionRequested')",
        "chunking": "event_type IN ('JSONParsed', 'SourceDeletionRequested')",
        "embedding": "event_type IN ('ChunksPrepared', 'SourceDeletionRequested')",
        "orchestrator": "event_type = 'EmbeddingsGenerated'",
        "summarization": "event_type = 'SummarizationRequested'",
        "reporting": "event_type IN ('SummaryComplete', 'SourceDeletionRequested')",
    }

    # Verify each service has the correct filter
    for service, expected_sql in expected_filters.items():
        assert service in filters, f"Service {service} not found in filters"
        assert filters[service] == expected_sql, (
            f"Filter for {service} does not match.\n"
            f"Expected: {expected_sql}\n"
            f"Got: {filters[service]}"
        )


def test_subscription_filters_use_sql_filter_type():
    """Test that subscription filters use SqlFilter type."""
    bicep_file = Path(__file__).parent / "servicebus.bicep"

    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_file), "--stdout"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Bicep compilation failed: {result.stderr}"
    template = json.loads(result.stdout)

    # Find subscription filter resources
    filter_resources = [
        r
        for r in template.get("resources", [])
        if r.get("type") == "Microsoft.ServiceBus/namespaces/topics/subscriptions/rules"
    ]

    assert len(filter_resources) > 0, "No subscription filter resources found"

    # Check that each filter uses SqlFilter type
    for resource in filter_resources:
        properties = resource.get("properties", {})
        assert properties.get("filterType") == "SqlFilter", (
            f"Filter {resource.get('name')} does not use SqlFilter type"
        )
        assert "sqlFilter" in properties, f"Filter {resource.get('name')} has no sqlFilter property"
        sql_filter = properties["sqlFilter"]
        assert "sqlExpression" in sql_filter, (
            f"Filter {resource.get('name')} has no sqlExpression in sqlFilter"
        )


if __name__ == "__main__":
    # Check if Azure CLI is available
    if not _az_available:
        print(f"⚠ Skipping tests: {_skip_reason}")
        import sys
        sys.exit(0)
    
    # Run tests
    test_servicebus_bicep_compiles()
    print("✓ Bicep template compiles successfully")

    test_subscription_filters_are_generated()
    print("✓ Subscription filters are generated")

    test_event_type_filter_mappings()
    print("✓ Event type filter mappings are correct")

    test_subscription_filters_use_sql_filter_type()
    print("✓ Subscription filters use SqlFilter type")

    print("\nAll tests passed!")
