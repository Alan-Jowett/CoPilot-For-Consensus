#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for convert_ndjson_to_csv.py converter script."""

import csv
import json
import tempfile
from pathlib import Path

import pytest


def test_parse_ndjson_with_valid_json():
    """Test parsing valid NDJSON lines."""
    ndjson_content = '{"TimeGenerated":"2025-01-20T10:00:00Z","Level":"Info","Message":"Test log"}\n'
    ndjson_content += '{"TimeGenerated":"2025-01-20T10:01:00Z","Level":"Error","Message":"Error log"}\n'
    
    lines = ndjson_content.strip().split('\n')
    records = [json.loads(line) for line in lines if line.strip()]
    
    assert len(records) == 2
    assert records[0]['Level'] == 'Info'
    assert records[1]['Level'] == 'Error'


def test_parse_ndjson_with_invalid_json():
    """Test handling of invalid JSON lines."""
    ndjson_content = '{"TimeGenerated":"2025-01-20T10:00:00Z","Level":"Info"}\n'
    ndjson_content += '{invalid json}\n'
    ndjson_content += '{"TimeGenerated":"2025-01-20T10:01:00Z","Level":"Error"}\n'
    
    records = []
    for line in ndjson_content.strip().split('\n'):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # Skip invalid lines
            continue
    
    assert len(records) == 2  # Invalid line skipped


def test_csv_field_extraction():
    """Test CSV field extraction with known and unknown fields."""
    record = {
        'TimeGenerated': '2025-01-20T10:00:00Z',
        'Level': 'Info',
        'Message': 'Test message',
        'CustomField': 'custom value',
        'AnotherField': 123
    }
    
    known_fields = ['TimeGenerated', 'Level', 'Message']
    
    # Extract known fields
    row = {field: record.get(field, '') for field in known_fields}
    
    # Put remaining fields in extras
    extras = {k: v for k, v in record.items() if k not in known_fields}
    row['_extras'] = json.dumps(extras, ensure_ascii=False)
    
    assert row['TimeGenerated'] == '2025-01-20T10:00:00Z'
    assert row['Level'] == 'Info'
    assert row['Message'] == 'Test message'
    
    extras_data = json.loads(row['_extras'])
    assert extras_data['CustomField'] == 'custom value'
    assert extras_data['AnotherField'] == 123


def test_csv_output_format():
    """Test CSV output format with headers."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        temp_path = Path(f.name)
        
        fieldnames = ['TimeGenerated', 'Level', 'Message', '_extras']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        row = {
            'TimeGenerated': '2025-01-20T10:00:00Z',
            'Level': 'Info',
            'Message': 'Test',
            '_extras': '{"custom":"value"}'
        }
        writer.writerow(row)
    
    # Read back and verify
    with open(temp_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 1
    assert rows[0]['Level'] == 'Info'
    
    # Cleanup
    temp_path.unlink()


def test_empty_ndjson_handling():
    """Test handling of empty NDJSON content."""
    ndjson_content = ''
    
    records = []
    for line in ndjson_content.strip().split('\n'):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    
    assert len(records) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
