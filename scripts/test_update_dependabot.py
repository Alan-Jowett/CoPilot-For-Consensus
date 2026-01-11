#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for update-dependabot.py

Tests the Dependabot configuration generator functionality.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path and import the module
sys.path.insert(0, os.path.dirname(__file__))

# Import the module by loading it directly
script_path = Path(__file__).parent / "update-dependabot.py"
with open(script_path) as f:
    code = compile(f.read(), script_path, 'exec')
    update_dependabot = {}
    exec(code, update_dependabot)

# Extract functions
find_python_packages = update_dependabot['find_python_packages']
generate_pip_update_entry = update_dependabot['generate_pip_update_entry']
generate_dependabot_config = update_dependabot['generate_dependabot_config']


def test_generate_pip_update_entry_basic():
    """Test that generate_pip_update_entry generates correct YAML structure."""
    result = generate_pip_update_entry(
        "Test Services",
        ["/service1", "/service2"],
        "services"
    )
    
    # Verify key components are present
    assert "# Monitor Python dependencies - Test Services" in result
    assert 'package-ecosystem: "pip"' in result
    assert 'directories:' in result
    assert '- "/service1"' in result
    assert '- "/service2"' in result
    assert 'interval: "weekly"' in result
    assert 'open-pull-requests-limit: 10' in result
    assert '- "dependencies"' in result
    assert '- "python"' in result
    assert '- "services"' in result
    assert 'pip-minor-patch:' in result
    assert '- "minor"' in result
    assert '- "patch"' in result


def test_generate_pip_update_entry_with_adapters_label():
    """Test that adapter label is correctly applied."""
    result = generate_pip_update_entry(
        "Adapters Group 1",
        ["/adapters/adapter1"],
        "adapters"
    )
    
    assert '- "adapters"' in result
    assert "# Monitor Python dependencies - Adapters Group 1" in result


def test_generate_pip_update_entry_empty_directories():
    """Test that function handles empty directory list."""
    result = generate_pip_update_entry(
        "Empty Group",
        [],
        "services"
    )
    
    # Should still generate valid YAML structure even with no directories
    assert 'package-ecosystem: "pip"' in result
    assert 'directories:' in result


def test_find_python_packages_with_requirements():
    """Test finding packages with requirements.txt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a service with requirements.txt
        service_dir = tmppath / "service1"
        service_dir.mkdir()
        (service_dir / "requirements.txt").write_text("requests==2.28.0\n")
        
        packages = find_python_packages(tmppath)
        
        assert len(packages) == 1
        assert packages[0][0] == "/service1"
        assert "service1 service" in packages[0][1]


def test_find_python_packages_with_requirements_in():
    """Test finding packages with requirements.in."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a service with requirements.in
        service_dir = tmppath / "service1"
        service_dir.mkdir()
        (service_dir / "requirements.in").write_text("requests\n")
        
        packages = find_python_packages(tmppath)
        
        assert len(packages) == 1
        assert packages[0][0] == "/service1"


def test_find_python_packages_with_setup_py():
    """Test finding packages with setup.py."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a service with setup.py
        service_dir = tmppath / "service1"
        service_dir.mkdir()
        (service_dir / "setup.py").write_text("from setuptools import setup\n")
        
        packages = find_python_packages(tmppath)
        
        assert len(packages) == 1
        assert packages[0][0] == "/service1"


def test_find_python_packages_excludes_hidden():
    """Test that hidden directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create a package in .git directory (should be excluded)
        git_dir = tmppath / ".git" / "subdir"
        git_dir.mkdir(parents=True)
        (git_dir / "requirements.txt").write_text("requests\n")
        
        packages = find_python_packages(tmppath)
        
        # Should not find the package in .git
        assert len(packages) == 0


def test_find_python_packages_adapter_description():
    """Test that adapters get correct description."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create an adapter
        adapter_dir = tmppath / "adapters" / "my_adapter"
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "requirements.txt").write_text("requests\n")
        
        packages = find_python_packages(tmppath)
        
        assert len(packages) == 1
        assert packages[0][0] == "/adapters/my_adapter"
        assert "my_adapter adapter" in packages[0][1]


def test_find_python_packages_sorting():
    """Test that packages are sorted with services first, then adapters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create adapters and services
        adapter_dir = tmppath / "adapters" / "adapter1"
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "requirements.txt").write_text("requests\n")
        
        service_dir = tmppath / "service1"
        service_dir.mkdir()
        (service_dir / "requirements.txt").write_text("requests\n")
        
        packages = find_python_packages(tmppath)
        
        # Services should come before adapters
        assert len(packages) == 2
        assert "/service1" in packages[0][0]
        assert "/adapters/adapter1" in packages[1][0]


def test_directory_splitting_logic():
    """Test that directories are correctly split into services and adapter groups."""
    packages = [
        ("/service1", "service1 service"),
        ("/service2", "service2 service"),
        ("/adapters/adapter1", "adapter1 adapter"),
        ("/adapters/adapter2", "adapter2 adapter"),
        ("/adapters/adapter3", "adapter3 adapter"),
    ]
    
    config = generate_dependabot_config(packages)
    
    # Verify services section exists
    assert "/service1" in config
    assert "/service2" in config
    
    # Verify adapters are split
    assert "/adapters/adapter1" in config
    assert "/adapters/adapter2" in config
    assert "/adapters/adapter3" in config
    
    # Verify group labels
    assert '"services"' in config
    assert '"adapters"' in config


def test_empty_services_list_handling():
    """Test that empty services list is properly handled."""
    packages = [
        ("/adapters/adapter1", "adapter1 adapter"),
        ("/adapters/adapter2", "adapter2 adapter"),
    ]
    
    config = generate_dependabot_config(packages)
    
    # Should only have adapter sections, no services section
    assert "/adapters/adapter1" in config
    assert "/adapters/adapter2" in config
    # Should not have a "Core Services" heading or services label
    assert "Monitor Python dependencies - Core Services" not in config
    # Verify we don't have the services label in any pip entry
    lines = config.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == '- "services"':
            # If we find it, check it's not in a pip section
            assert False, "Found unexpected 'services' label in config"


def test_empty_adapters_list_handling():
    """Test that empty adapters list is properly handled."""
    packages = [
        ("/service1", "service1 service"),
        ("/service2", "service2 service"),
    ]
    
    config = generate_dependabot_config(packages)
    
    # Should only have services section, no adapter sections
    assert "/service1" in config
    assert "/service2" in config
    # Should not have adapter group headings
    assert "Adapters Group 1" not in config
    assert "Adapters Group 2" not in config


def test_odd_number_of_adapters():
    """Test that odd number of adapters are split correctly (group 2 gets extra)."""
    packages = [
        ("/adapters/adapter1", "adapter1 adapter"),
        ("/adapters/adapter2", "adapter2 adapter"),
        ("/adapters/adapter3", "adapter3 adapter"),
    ]
    
    config = generate_dependabot_config(packages)
    
    # All adapters should be present
    assert "/adapters/adapter1" in config
    assert "/adapters/adapter2" in config
    assert "/adapters/adapter3" in config
    
    # Should have both adapter groups
    assert "Adapters Group 1" in config
    assert "Adapters Group 2" in config


def test_generated_config_includes_npm():
    """Test that generated config includes npm monitoring."""
    packages = [("/service1", "service1 service")]
    
    config = generate_dependabot_config(packages)
    
    assert "# Monitor npm dependencies in React UI" in config
    assert 'package-ecosystem: "npm"' in config
    assert 'directory: "/ui"' in config


def test_generated_config_includes_docker():
    """Test that generated config includes docker monitoring."""
    packages = [("/service1", "service1 service")]
    
    config = generate_dependabot_config(packages)
    
    assert "# Monitor Docker image updates in docker-compose" in config
    assert 'package-ecosystem: "docker"' in config


def test_generated_config_includes_github_actions():
    """Test that generated config includes GitHub Actions monitoring."""
    packages = [("/service1", "service1 service")]
    
    config = generate_dependabot_config(packages)
    
    assert "# Monitor GitHub Actions" in config
    assert 'package-ecosystem: "github-actions"' in config


def test_generated_config_has_timeout_reference():
    """Test that generated config includes reference to timeout issue."""
    packages = [("/service1", "service1 service")]
    
    config = generate_dependabot_config(packages)
    
    assert "Split into multiple entries to prevent Dependabot timeout" in config
    assert "https://github.com/orgs/community/discussions/179358" in config


def test_generated_config_has_header():
    """Test that generated config includes proper header."""
    packages = [("/service1", "service1 service")]
    
    config = generate_dependabot_config(packages)
    
    assert "SPDX-License-Identifier: MIT" in config
    assert "THIS FILE IS AUTO-GENERATED" in config
    assert "version: 2" in config
    assert "updates:" in config


if __name__ == '__main__':
    # Try to use pytest if available, otherwise run tests manually
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to manual execution - discover and run all test functions
        import inspect
        current_module = sys.modules[__name__]
        test_functions = [
            func for name, func in inspect.getmembers(current_module, inspect.isfunction)
            if name.startswith('test_')
        ]
        
        failed_tests = []
        for test_func in test_functions:
            try:
                test_func()
                print(f"✓ {test_func.__name__}")
            except AssertionError as e:
                print(f"✗ {test_func.__name__}: {e}")
                failed_tests.append(test_func.__name__)
            except Exception as e:
                print(f"✗ {test_func.__name__}: Unexpected error: {e}")
                failed_tests.append(test_func.__name__)
        
        if failed_tests:
            print(f"\n{len(failed_tests)} test(s) failed:")
            for name in failed_tests:
                print(f"  - {name}")
            sys.exit(1)
        else:
            print(f"\nAll {len(test_functions)} tests passed!")
