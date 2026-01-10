#!/usr/bin/env python3
"""Fix test_service.py to use proper DriverConfig pattern."""

import re

with open('ingestion/tests/test_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix base_publisher
content = content.replace(
    'base_publisher = create_publisher(driver_name="noop")',
    'base_publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})\n        base_publisher = create_publisher(driver_name="noop", driver_config=base_publisher_config)'
)

# Fix metrics
content = content.replace(
    'metrics = create_metrics_collector(driver_name="noop")',
    'metrics_config = load_driver_config(service=None, adapter="metrics", driver="noop", fields={})\n        metrics = create_metrics_collector(driver_name="noop", driver_config=metrics_config)'
)

# Fix document_store
content = content.replace(
    'document_store = create_document_store(driver_name="inmemory")',
    'store_config = load_driver_config(service=None, adapter="storage", driver="inmemory", fields={})\n        document_store = create_document_store(driver_name="inmemory", driver_config=store_config)'
)

# Fix standalone publisher calls
content = re.sub(
    r'(\n    )publisher = create_publisher\(driver_name="noop"\)',
    r'\1publisher_config = load_driver_config(service=None, adapter="message_bus", driver="noop", fields={})\n    publisher = create_publisher(driver_name="noop", driver_config=publisher_config)',
    content
)

# Fix ArchiveMetadata imports
content = content.replace(
    'from copilot_message_bus import ArchiveMetadata',
    'from copilot_schema_validation import ArchiveMetadata'
)

with open('ingestion/tests/test_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed test_service.py")
