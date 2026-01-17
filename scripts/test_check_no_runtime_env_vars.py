#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for check_no_runtime_env_vars.py

Tests the runtime environment variables checker functionality.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))

from check_no_runtime_env_vars import check_file, is_allowlisted, load_allowlist


def test_detect_os_environ_get():
    """Test detection of os.environ.get()."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('import os\ndef bad_func():\n    value = os.environ.get("VAR")\n')
        f.flush()
        filepath = Path(f.name)

    try:
        violations = check_file(filepath)
        assert len(violations) == 1
        assert 'os.environ.get' in violations[0][1]
    finally:
        filepath.unlink()


def test_detect_os_getenv():
    """Test detection of os.getenv()."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('import os\ndef bad_func():\n    value = os.getenv("VAR")\n')
        f.flush()
        filepath = Path(f.name)

    try:
        violations = check_file(filepath)
        assert len(violations) == 1
        assert 'os.getenv' in violations[0][1]
    finally:
        filepath.unlink()


def test_detect_os_environ_bracket():
    """Test detection of os.environ[]."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('import os\ndef bad_func():\n    value = os.environ["VAR"]\n')
        f.flush()
        filepath = Path(f.name)

    try:
        violations = check_file(filepath)
        assert len(violations) == 1
        assert 'os.environ[' in violations[0][1]
    finally:
        filepath.unlink()


def test_no_false_positives():
    """Test that normal code doesn't trigger false positives."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import os
from copilot_config.runtime_loader import get_config

def good_func():
    config = get_config("myservice")
    value = config.service_settings.some_value
    return value
''')
        f.flush()
        filepath = Path(f.name)

    try:
        violations = check_file(filepath)
        assert len(violations) == 0
    finally:
        filepath.unlink()


def test_allowlist_entire_file():
    """Test that allowlisting entire file works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test file
        test_file = tmpdir_path / "test.py"
        test_file.write_text('import os\nvalue = os.environ.get("VAR")\n')
        
        # Create allowlist
        allowlist_file = tmpdir_path / "allowlist.txt"
        allowlist_file.write_text("test.py\n")
        
        # Load allowlist
        allowlist = load_allowlist(allowlist_file)
        
        # Check that violation is allowlisted
        is_allowed = is_allowlisted(
            test_file,
            'value = os.environ.get("VAR")',
            allowlist,
            tmpdir_path
        )
        assert is_allowed


def test_allowlist_with_regex():
    """Test that allowlisting with regex pattern works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test file
        test_file = tmpdir_path / "test.py"
        test_file.write_text('import os\nvalue = os.environ.get("ALLOWED_VAR")\n')
        
        # Create allowlist with regex
        allowlist_file = tmpdir_path / "allowlist.txt"
        allowlist_file.write_text("test.py:ALLOWED_VAR\n")
        
        # Load allowlist
        allowlist = load_allowlist(allowlist_file)
        
        # Check that specific line is allowlisted
        is_allowed = is_allowlisted(
            test_file,
            'value = os.environ.get("ALLOWED_VAR")',
            allowlist,
            tmpdir_path
        )
        assert is_allowed
        
        # Check that line without the pattern is not allowlisted
        is_not_allowed = is_allowlisted(
            test_file,
            'value = os.environ.get("DIFFERENT_VAR")',
            allowlist,
            tmpdir_path
        )
        assert not is_not_allowed


def test_multiple_violations_in_file():
    """Test detection of multiple violations in single file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import os
def func1():
    a = os.environ.get("VAR1")
    b = os.getenv("VAR2")
    c = os.environ["VAR3"]
''')
        f.flush()
        filepath = Path(f.name)

    try:
        violations = check_file(filepath)
        assert len(violations) == 3
    finally:
        filepath.unlink()


def run_tests():
    """Run all tests."""
    tests = [
        test_detect_os_environ_get,
        test_detect_os_getenv,
        test_detect_os_environ_bracket,
        test_no_false_positives,
        test_allowlist_entire_file,
        test_allowlist_with_regex,
        test_multiple_violations_in_file,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1
    
    if failed > 0:
        print(f"\n{failed} test(s) failed")
        return 1
    else:
        print(f"\n✓ All {len(tests)} tests passed")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
