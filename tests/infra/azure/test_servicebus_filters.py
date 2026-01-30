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
import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore


# Check if Azure CLI with Bicep is available
def _check_az_available():
    """Check if 'az' CLI with Bicep component is available on PATH."""
    if shutil.which("az") is None:
        return False

    # Verify Bicep component is installed
    try:
        result = subprocess.run(
            ["az", "bicep", "version"],
            capture_output=True,
            timeout=10,
            text=True,
        )
        # Only treat Bicep as available if the command succeeds
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# Skip all tests if Azure CLI is not available
_az_available = _check_az_available()
_skip_reason = "Azure CLI (az) with bicep component not found on PATH. Install with: az bicep install"

if pytest:
    pytestmark = pytest.mark.skipif(not _az_available, reason=_skip_reason)


def _compile_bicep_to_json():
    """Helper function to compile Bicep template to JSON.

    Returns:
        dict: Parsed JSON template from Bicep compilation

    Raises:
        RuntimeError: If compilation fails, output is invalid, or JSON parsing fails
    """
    # Path to servicebus.bicep relative to this test file
    # Test is in tests/infra/azure/, Bicep is in infra/azure/modules/
    # Go up 4 levels to repo root, then down to infra/azure/modules/
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    bicep_file = repo_root / "infra" / "azure" / "modules" / "servicebus.bicep"
    if not bicep_file.exists():
        raise RuntimeError(f"servicebus.bicep not found at {bicep_file}")

    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(bicep_file), "--stdout"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Bicep compilation failed: {result.stderr}")

    if not result.stdout:
        raise RuntimeError("Expected JSON output from Bicep compilation")

    try:
        template = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as e:
        # Show first 200 chars of output to help debug
        output_snippet = result.stdout[:200] if result.stdout else "(empty)"
        raise RuntimeError(f"Failed to parse Bicep output as JSON: {e}. Output: {output_snippet}")

    if not template:
        raise RuntimeError("Failed to parse compiled Bicep template")

    return template


# Pytest fixture to compile Bicep once and reuse across tests
if pytest:
    @pytest.fixture(scope="module")
    def compiled_template():
        """Compile the Bicep template once and return the parsed JSON."""
        return _compile_bicep_to_json()


def test_servicebus_bicep_compiles(compiled_template=None):
    """Test that the servicebus.bicep template compiles without errors."""
    if compiled_template is None:
        # Fallback for standalone execution
        compiled_template = _compile_bicep_to_json()

    assert compiled_template, "Failed to parse compiled Bicep template"


def test_subscription_filters_are_generated(compiled_template=None):
    """Test that SQL filter rules are generated for each service subscription."""
    if compiled_template is None:
        # Fallback for standalone execution
        compiled_template = _compile_bicep_to_json()

    # Find subscription filter resources
    filter_resources = [
        r
        for r in compiled_template.get("resources", [])
        if r.get("type") == "Microsoft.ServiceBus/namespaces/topics/subscriptions/rules"
    ]

    # In the compiled template, Bicep uses a copy loop, so there's one resource definition
    # that gets deployed multiple times (once per receiverService)
    assert len(filter_resources) > 0, "No subscription filter resources found"

    # Check that the resource has a copy element for multiple instances
    filter_resource = filter_resources[0]
    assert "copy" in filter_resource, "Filter resource should have a copy element for multiple instances"

    # Verify the copy count expression references receiverServices (one instance per receiver service)
    copy_count = filter_resource["copy"]["count"]
    copy_count_str = str(copy_count)
    # The count is an expression like "[length(parameters('receiverServices'))]"
    assert "receiverServices" in copy_count_str, f"Copy count should reference receiverServices: {copy_count_str}"

    # Verify the rule is named $Default (replaces the default TrueFilter)
    assert "$Default" in str(filter_resource.get("name")), "Filter not named $Default"


def test_event_type_filter_mappings(compiled_template=None):
    """Test that the event type filter mappings are correct for each service."""
    if compiled_template is None:
        # Fallback for standalone execution
        compiled_template = _compile_bicep_to_json()

    # Verify the serviceEventTypeFilters variable exists
    variables = compiled_template.get("variables", {})
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


def test_subscription_filters_use_sql_filter_type(compiled_template=None):
    """Test that subscription filters use SqlFilter type."""
    if compiled_template is None:
        # Fallback for standalone execution
        compiled_template = _compile_bicep_to_json()

    # Find subscription filter resources
    filter_resources = [
        r
        for r in compiled_template.get("resources", [])
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


def test_subscription_filters_have_safe_fallback(compiled_template=None):
    """Test that subscription filters use safe access with deny-all fallback.

    The Bicep template should use safe access (?[]) with null-coalescing (??)
    to fall back to a deny-all filter (1=0) if receiverServices contains an
    unknown service. This ensures misconfiguration fails closed.
    """
    if compiled_template is None:
        # Fallback for standalone execution
        compiled_template = _compile_bicep_to_json()

    # Find subscription filter resources
    filter_resources = [
        r
        for r in compiled_template.get("resources", [])
        if r.get("type") == "Microsoft.ServiceBus/namespaces/topics/subscriptions/rules"
    ]

    assert len(filter_resources) > 0, "No subscription filter resources found"

    # The sqlExpression should be an ARM expression using coalesce for safe fallback
    # When compiled from Bicep, ?[] ?? '1=0' becomes coalesce(..., '1=0')
    filter_resource = filter_resources[0]
    sql_expression = str(filter_resource.get("properties", {}).get("sqlFilter", {}).get("sqlExpression", ""))

    # The expression should include the fallback value '1=0' for deny-all
    assert "1=0" in sql_expression, (
        f"sqlExpression should include deny-all fallback '1=0' for unknown services. "
        f"Got: {sql_expression}"
    )


if __name__ == "__main__":
    # Standalone execution should use pytest to ensure assertion checks work
    # even under python -O (which strips assert statements)
    if pytest is None:
        print("❌ pytest is required to run these tests. Install with: pip install pytest")
        sys.exit(1)

    # Delegate to pytest so assertion rewriting works even under python -O
    exit_code = pytest.main([str(Path(__file__)), "-v"])
    sys.exit(exit_code)
