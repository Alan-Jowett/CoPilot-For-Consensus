# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for reporting-ui service configuration."""

import pytest
import os
import sys

# Add parent directory to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_config_schema_exists():
    """Test that the config schema file exists."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'documents',
        'schemas',
        'configs',
        'reporting-ui.json'
    )
    assert os.path.exists(schema_path), f"Config schema not found at {schema_path}"


def test_required_files_exist():
    """Test that all required files exist."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    required_files = [
        'main.py',
        'requirements.txt',
        'Dockerfile',
        'README.md',
        'pytest.ini',
        'templates/reports_list.html',
        'templates/report_detail.html',
        'templates/thread_summary.html',
        'templates/error.html',
    ]
    
    for file_path in required_files:
        full_path = os.path.join(base_dir, file_path)
        assert os.path.exists(full_path), f"Required file not found: {file_path}"


def test_dockerfile_structure():
    """Test that Dockerfile has expected structure."""
    dockerfile_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'Dockerfile'
    )
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Check for key elements
    assert 'FROM python:3.11-slim' in content
    assert 'copilot_config' in content
    assert 'copilot_logging' in content
    assert 'EXPOSE 8083' in content
    assert 'CMD ["python", "main.py"]' in content
