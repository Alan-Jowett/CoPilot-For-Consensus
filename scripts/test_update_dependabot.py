#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for update-dependabot.py

Tests the dependabot configuration generation functionality, particularly
the find_dockerfiles() function that discovers Dockerfile directories.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import with hyphen replaced by underscore
import importlib.util
spec = importlib.util.spec_from_file_location("update_dependabot", Path(__file__).parent / "update-dependabot.py")
update_dependabot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_dependabot)

find_dockerfiles = update_dependabot.find_dockerfiles


def test_find_dockerfiles_root_only():
    """Test that root directory is always included even without Dockerfiles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Don't create any Dockerfiles, just empty directory
        result = find_dockerfiles(tmppath)
        
        # Root should always be included for docker-compose files
        assert '/' in result
        assert len(result) == 1


def test_find_dockerfiles_basic():
    """Test detection of Dockerfile in subdirectory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a service directory with Dockerfile
        service_dir = tmppath / 'myservice'
        service_dir.mkdir()
        (service_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        assert '/' in result
        assert '/myservice' in result
        assert len(result) == 2


def test_find_dockerfiles_nested():
    """Test detection of Dockerfiles in nested directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create nested directories with Dockerfiles
        infra_dir = tmppath / 'infra'
        infra_dir.mkdir()
        
        exporter_dir = infra_dir / 'exporter'
        exporter_dir.mkdir()
        (exporter_dir / 'Dockerfile').write_text('FROM alpine\n')
        
        result = find_dockerfiles(tmppath)
        
        assert '/' in result
        assert '/infra/exporter' in result
        assert len(result) == 2


def test_find_dockerfiles_with_suffix():
    """Test detection of Dockerfiles with suffixes (e.g., Dockerfile.retry-job)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        scripts_dir = tmppath / 'scripts'
        scripts_dir.mkdir()
        (scripts_dir / 'Dockerfile.retry-job').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        assert '/' in result
        assert '/scripts' in result
        assert len(result) == 2


def test_find_dockerfiles_excludes_git():
    """Test that .git directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create .git directory with a Dockerfile (should be ignored)
        git_dir = tmppath / '.git'
        git_dir.mkdir()
        (git_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should only have root, not .git
        assert '/' in result
        assert '/.git' not in result
        assert len(result) == 1


def test_find_dockerfiles_excludes_node_modules():
    """Test that node_modules directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create node_modules directory with a Dockerfile (should be ignored)
        node_dir = tmppath / 'node_modules'
        node_dir.mkdir()
        (node_dir / 'Dockerfile').write_text('FROM node:18\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should only have root, not node_modules
        assert '/' in result
        assert '/node_modules' not in result
        assert len(result) == 1


def test_find_dockerfiles_excludes_venv():
    """Test that virtual environment directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create various venv directories
        for venv_name in ['.venv', 'venv', 'env']:
            venv_dir = tmppath / venv_name
            venv_dir.mkdir()
            (venv_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should only have root, not any venv directories
        assert '/' in result
        assert '/.venv' not in result
        assert '/venv' not in result
        assert '/env' not in result
        assert len(result) == 1


def test_find_dockerfiles_includes_infra():
    """Test that infra directory is included (unlike Python package search)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create infra directory with Dockerfile
        infra_dir = tmppath / 'infra'
        infra_dir.mkdir()
        
        mongodb_dir = infra_dir / 'mongodb-exporter'
        mongodb_dir.mkdir()
        (mongodb_dir / 'Dockerfile').write_text('FROM prom/mongodb-exporter\n')
        
        result = find_dockerfiles(tmppath)
        
        # infra should be included for Dockerfiles
        assert '/' in result
        assert '/infra/mongodb-exporter' in result
        assert len(result) == 2


def test_find_dockerfiles_multiple_services():
    """Test detection of multiple service directories with Dockerfiles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create multiple service directories
        services = ['auth', 'chunking', 'embedding', 'ingestion']
        for service in services:
            service_dir = tmppath / service
            service_dir.mkdir()
            (service_dir / 'Dockerfile').write_text(f'FROM python:3.11\n# {service} service\n')
        
        result = find_dockerfiles(tmppath)
        
        # Root + 4 services = 5 directories
        assert len(result) == 5
        assert '/' in result
        for service in services:
            assert f'/{service}' in result


def test_find_dockerfiles_sorted():
    """Test that results are sorted alphabetically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create directories in non-alphabetical order
        for service in ['zebra', 'alpha', 'beta']:
            service_dir = tmppath / service
            service_dir.mkdir()
            (service_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        # Check that results are sorted (/ should be first, then alphabetical)
        assert result == ['/', '/alpha', '/beta', '/zebra']


def test_find_dockerfiles_cross_platform_paths():
    """Test that paths are converted to Unix-style forward slashes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create nested directory
        nested = tmppath / 'level1' / 'level2'
        nested.mkdir(parents=True)
        (nested / 'Dockerfile').write_text('FROM alpine\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should use forward slashes regardless of OS
        assert '/level1/level2' in result
        # Should not contain backslashes (Windows paths)
        for path in result:
            assert '\\' not in path


def test_find_dockerfiles_no_duplicates():
    """Test that duplicate directories are not included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create directory with multiple Dockerfiles
        service_dir = tmppath / 'myservice'
        service_dir.mkdir()
        (service_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        (service_dir / 'Dockerfile.dev').write_text('FROM python:3.11\n')
        (service_dir / 'Dockerfile.prod').write_text('FROM python:3.11\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should only include the directory once
        assert result.count('/myservice') == 1
        assert len(result) == 2  # / and /myservice


def test_find_dockerfiles_excludes_documents():
    """Test that documents directory is excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create documents directory with a Dockerfile (should be ignored)
        docs_dir = tmppath / 'documents'
        docs_dir.mkdir()
        (docs_dir / 'Dockerfile').write_text('FROM nginx\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should only have root, not documents
        assert '/' in result
        assert '/documents' not in result
        assert len(result) == 1


def test_find_dockerfiles_empty_directory():
    """Test behavior with an empty directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create some empty subdirectories
        (tmppath / 'empty1').mkdir()
        (tmppath / 'empty2').mkdir()
        
        result = find_dockerfiles(tmppath)
        
        # Should only have root
        assert result == ['/']


def test_find_dockerfiles_mixed_content():
    """Test directory with mix of Dockerfiles and other files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create service directory with various files
        service_dir = tmppath / 'myservice'
        service_dir.mkdir()
        (service_dir / 'Dockerfile').write_text('FROM python:3.11\n')
        (service_dir / 'requirements.txt').write_text('flask==2.0.0\n')
        (service_dir / 'main.py').write_text('print("hello")\n')
        (service_dir / 'README.md').write_text('# Service\n')
        
        result = find_dockerfiles(tmppath)
        
        # Should still detect the directory even with other files
        assert '/' in result
        assert '/myservice' in result
        assert len(result) == 2


if __name__ == '__main__':
    # Try to use pytest if available, otherwise run tests manually
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to manual execution if pytest is not available
        test_find_dockerfiles_root_only()
        test_find_dockerfiles_basic()
        test_find_dockerfiles_nested()
        test_find_dockerfiles_with_suffix()
        test_find_dockerfiles_excludes_git()
        test_find_dockerfiles_excludes_node_modules()
        test_find_dockerfiles_excludes_venv()
        test_find_dockerfiles_includes_infra()
        test_find_dockerfiles_multiple_services()
        test_find_dockerfiles_sorted()
        test_find_dockerfiles_cross_platform_paths()
        test_find_dockerfiles_no_duplicates()
        test_find_dockerfiles_excludes_documents()
        test_find_dockerfiles_empty_directory()
        test_find_dockerfiles_mixed_content()
        print("All tests passed!")
