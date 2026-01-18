#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""CLI script for validating and inspecting the schema registry.

This script provides utilities for:
- Validating that all registered schemas exist and are valid JSON
- Listing all registered schemas in a human-readable format
- Generating markdown documentation of available schemas
"""

import argparse
import logging

from copilot_schema_validation.schema_registry import (
    SCHEMA_REGISTRY,
    get_schema_metadata,
    list_schemas,
    validate_registry,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def validate_command() -> int:
    """Validate all registered schemas.

    Returns:
        Exit code: 0 if all schemas are valid, 1 if any validation errors.
    """
    logger.info("Validating schema registry...")
    valid, errors = validate_registry()

    if valid:
        logger.info(f"✓ All {len(SCHEMA_REGISTRY)} registered schemas are valid")
        return 0
    else:
        logger.error(f"✗ Schema registry validation failed with {len(errors)} error(s):")
        for error in errors:
            logger.error(f"  - {error}")
        return 1


def list_command(format: str = "table") -> int:
    """List all registered schemas.

    Args:
        format: Output format ('table', 'csv', or 'json')

    Returns:
        Exit code: always 0
    """
    schemas = list_schemas()

    if format == "csv":
        print("Type,Version,Path")
        for schema_type, version, path in schemas:
            print(f"{schema_type},{version},{path}")

    elif format == "json":
        import json

        output = [{"type": t, "version": v, "path": p} for t, v, p in schemas]
        print(json.dumps(output, indent=2))

    else:  # table format
        # Calculate column widths
        if not schemas:
            print("No schemas found")
            return 0

        max_type_len = max(len(t) for t, _, _ in schemas)
        max_version_len = max(len(v) for t, v, _ in schemas)
        max_path_len = max(len(p) for _, _, p in schemas)

        # Print header
        header = f"{'Type':<{max_type_len}}  {'Version':<{max_version_len}}  {'Path':<{max_path_len}}"
        print(header)
        print("-" * len(header))

        # Print rows
        for schema_type, version, path in schemas:
            print(f"{schema_type:<{max_type_len}}  {version:<{max_version_len}}  {path:<{max_path_len}}")

        print(f"\nTotal: {len(schemas)} schemas")

    return 0


def markdown_command() -> int:
    """Generate markdown documentation of registered schemas.

    Returns:
        Exit code: always 0
    """
    schemas = list_schemas()

    # Group schemas by category in a single pass
    events = []
    documents = []
    role_store = []
    others = []

    for schema in schemas:
        path = schema[2]
        if "events/" in path:
            events.append(schema)
        elif "documents/" in path:
            documents.append(schema)
        elif "role_store/" in path:
            role_store.append(schema)
        else:
            others.append(schema)

    print("# Schema Registry")
    print()
    print("This document lists all registered schemas in the Copilot-for-Consensus system.")
    print()
    print(f"**Total schemas:** {len(schemas)}")
    print()

    def print_table(schemas_list: list[tuple[str, str, str]], title: str):
        """Print a markdown table for a category of schemas."""
        if not schemas_list:
            return

        print(f"## {title}")
        print()
        print("| Type | Version | Path |")
        print("|------|---------|------|")
        for schema_type, version, path in schemas_list:
            print(f"| {schema_type} | {version} | `{path}` |")
        print()

    print_table(events, "Event Schemas")
    print_table(documents, "Document Schemas")
    print_table(role_store, "Role Store Schemas")
    print_table(others, "Other Schemas")

    print("## Usage Examples")
    print()
    print("```python")
    print("from copilot_schema_validation import load_schema, get_schema_path")
    print()
    print("# Load a schema")
    print('schema = load_schema("ArchiveIngested", "v1")')
    print()
    print("# Get the path to a schema file")
    print('path = get_schema_path("Archive", "v1")')
    print("```")
    print()

    return 0


def info_command(schema_type: str, version: str) -> int:
    """Show detailed information about a specific schema.

    Args:
        schema_type: The schema type name
        version: The schema version

    Returns:
        Exit code: 0 if schema exists, 1 if not found
    """
    metadata = get_schema_metadata(schema_type, version)

    if metadata is None:
        logger.error(f"Schema not found: {schema_type} {version}")
        logger.info("Run 'validate_schema_registry.py list' to see available schemas")
        return 1

    print(f"Schema: {schema_type} (version {version})")
    print(f"  Relative path: {metadata['relative_path']}")
    print(f"  Absolute path: {metadata['absolute_path']}")
    print(f"  Exists: {'✓' if metadata['exists'] else '✗'}")

    if metadata["exists"]:
        # Try to load and show some basic info
        try:
            from copilot_schema_validation.schema_registry import load_schema

            schema = load_schema(schema_type, version)

            if "title" in schema:
                print(f"  Title: {schema['title']}")
            if "description" in schema:
                print(f"  Description: {schema['description']}")
            if "$id" in schema:
                print(f"  Schema ID: {schema['$id']}")

            # Count properties if it's an object schema
            if schema.get("type") == "object" and "properties" in schema:
                print(f"  Properties: {len(schema['properties'])}")
        except Exception as e:
            logger.warning(f"Could not load schema: {e}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate and inspect the schema registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all schemas
  %(prog)s validate

  # List all schemas in table format
  %(prog)s list

  # List schemas in CSV format
  %(prog)s list --format csv

  # Generate markdown documentation
  %(prog)s markdown > SCHEMAS.md

  # Show info about a specific schema
  %(prog)s info ArchiveIngested v1
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Validate command
    subparsers.add_parser("validate", help="Validate that all registered schemas exist and are valid")

    # List command
    list_parser = subparsers.add_parser("list", help="List all registered schemas")
    list_parser.add_argument(
        "--format", choices=["table", "csv", "json"], default="table", help="Output format (default: table)"
    )

    # Markdown command
    subparsers.add_parser("markdown", help="Generate markdown documentation of schemas")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show detailed information about a specific schema")
    info_parser.add_argument("type", help="Schema type name")
    info_parser.add_argument("version", help="Schema version (e.g., v1)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute the appropriate command
    if args.command == "validate":
        return validate_command()
    elif args.command == "list":
        return list_command(format=args.format)
    elif args.command == "markdown":
        return markdown_command()
    elif args.command == "info":
        return info_command(args.type, args.version)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
