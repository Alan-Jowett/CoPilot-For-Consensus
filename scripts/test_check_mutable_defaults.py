#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for check_mutable_defaults.py

Tests the mutable defaults checker functionality.
"""
import tempfile
from pathlib import Path
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))

from check_mutable_defaults import find_mutable_defaults, scan_directory


def test_detect_list_literal():
    """Test detection of list literal defaults."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(items=[]):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][1] == 'bad_func'
        assert issues[0][2] == 'items'
        assert issues[0][3] == 'list'
    finally:
        filepath.unlink()


def test_detect_dict_literal():
    """Test detection of dict literal defaults."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(config={}):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'config'
        assert issues[0][3] == 'dict'
    finally:
        filepath.unlink()


def test_detect_set_literal():
    """Test detection of set literal defaults."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(tags={1, 2, 3}):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'tags'
        assert issues[0][3] == 'set'
    finally:
        filepath.unlink()


def test_detect_list_call():
    """Test detection of list() constructor calls."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(items=list()):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'items'
        assert issues[0][3] == 'list'
    finally:
        filepath.unlink()


def test_detect_dict_call():
    """Test detection of dict() constructor calls."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(config=dict()):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'config'
        assert issues[0][3] == 'dict'
    finally:
        filepath.unlink()


def test_detect_set_call():
    """Test detection of set() constructor calls."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(tags=set()):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'tags'
        assert issues[0][3] == 'set'
    finally:
        filepath.unlink()


def test_ignore_none_defaults():
    """Test that None defaults are not flagged."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def good_func(items=None):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 0
    finally:
        filepath.unlink()


def test_ignore_immutable_defaults():
    """Test that immutable defaults are not flagged."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def good_func(value=42, name="test", flag=True):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 0
    finally:
        filepath.unlink()


def test_detect_async_functions():
    """Test detection in async functions."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('async def bad_func(items=[]):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][1] == 'bad_func'
    finally:
        filepath.unlink()


def test_detect_keyword_only_args():
    """Test detection in keyword-only arguments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(*, items=[]):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'items'
    finally:
        filepath.unlink()


def test_multiple_issues():
    """Test detection of multiple issues in one file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def func1(items=[]):
    pass

def func2(config={}):
    pass

def func3(tags=set()):
    pass
''')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 3
        func_names = {issue[1] for issue in issues}
        assert func_names == {'func1', 'func2', 'func3'}
    finally:
        filepath.unlink()


def test_scan_directory():
    """Test scanning a directory for issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a file with issues
        (tmppath / 'bad.py').write_text('def bad_func(items=[]):\n    pass\n')
        
        # Create a file without issues
        (tmppath / 'good.py').write_text('def good_func(items=None):\n    pass\n')
        
        # Create a file in a subdirectory
        subdir = tmppath / 'subdir'
        subdir.mkdir()
        (subdir / 'nested.py').write_text('def nested_bad(config={}):\n    pass\n')
        
        issues = scan_directory(tmppath, set())
        assert len(issues) == 2
        
        # Check that both files were found
        files = {str(issue[0].name) for issue in issues}
        assert 'bad.py' in files
        assert 'nested.py' in files


def test_exclude_patterns():
    """Test that excluded directories are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a file in a normal directory
        (tmppath / 'normal.py').write_text('def bad_func(items=[]):\n    pass\n')
        
        # Create a file in an excluded directory
        excluded_dir = tmppath / 'node_modules'
        excluded_dir.mkdir()
        (excluded_dir / 'excluded.py').write_text('def bad_func(items=[]):\n    pass\n')
        
        excludes = {'node_modules'}
        issues = scan_directory(tmppath, excludes)
        
        # Should only find the issue in normal.py
        assert len(issues) == 1
        assert issues[0][0].name == 'normal.py'


def test_detect_class_methods():
    """Test detection in class methods with mutable default arguments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
class MyClass:
    def method(self, items=[]):
        pass
''')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][1] == 'method'
        assert issues[0][2] == 'items'
    finally:
        filepath.unlink()


def test_detect_nested_functions():
    """Test detection in nested functions with mutable default arguments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
def outer():
    def inner(items=[]):
        pass
''')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][1] == 'inner'
        assert issues[0][2] == 'items'
    finally:
        filepath.unlink()


def test_detect_constructor_with_args():
    """Test detection of constructor calls with arguments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('def bad_func(items=list([1, 2, 3])):\n    pass\n')
        f.flush()
        filepath = Path(f.name)
    
    try:
        issues = find_mutable_defaults(filepath)
        assert len(issues) == 1
        assert issues[0][2] == 'items'
        assert issues[0][3] == 'list'
    finally:
        filepath.unlink()


if __name__ == '__main__':
    # Try to use pytest if available, otherwise run tests manually
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to manual execution if pytest is not available
        test_detect_list_literal()
        test_detect_dict_literal()
        test_detect_set_literal()
        test_detect_list_call()
        test_detect_dict_call()
        test_detect_set_call()
        test_ignore_none_defaults()
        test_ignore_immutable_defaults()
        test_detect_async_functions()
        test_detect_keyword_only_args()
        test_multiple_issues()
        test_scan_directory()
        test_exclude_patterns()
        test_detect_class_methods()
        test_detect_nested_functions()
        test_detect_constructor_with_args()
        print("All tests passed!")
