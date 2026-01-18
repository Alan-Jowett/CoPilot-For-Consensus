# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for install_adapters script functions."""

import tempfile
from pathlib import Path

import pytest
from install_adapters import _extras_from_setup, select_azure_extra


@pytest.fixture
def temp_adapter_dir():
    """Create a temporary adapter directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestExtrasFromSetup:
    """Test _extras_from_setup() function."""

    def test_parse_simple_extras(self, temp_adapter_dir):
        """Test parsing setup.py with simple extras_require."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "dev": ["pytest"],
        "azure": ["azure-core"],
    },
)
"""
        )

        extras = _extras_from_setup(setup_py)
        assert extras == {"dev", "azure"}

    def test_parse_multiple_extras(self, temp_adapter_dir):
        """Test parsing setup.py with multiple extras."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "dev": ["pytest>=7.0.0"],
        "test": ["pytest-cov>=4.0.0"],
        "azure": ["azure-monitor-opentelemetry-exporter==1.0.0b21"],
        "azuremonitor": ["azure-monitor-opentelemetry-exporter==1.0.0b21"],
        "all": ["pytest", "azure-core"],
    },
)
"""
        )

        extras = _extras_from_setup(setup_py)
        assert extras == {"dev", "test", "azure", "azuremonitor", "all"}

    def test_parse_empty_extras(self, temp_adapter_dir):
        """Test parsing setup.py with no extras_require."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    install_requires=["requests"],
)
"""
        )

        extras = _extras_from_setup(setup_py)
        assert extras == set()

    def test_missing_setup_file(self, temp_adapter_dir):
        """Test behavior with missing setup.py file."""
        setup_py = temp_adapter_dir / "setup.py"

        extras = _extras_from_setup(setup_py)
        assert extras == set()

    def test_malformed_setup_file(self, temp_adapter_dir):
        """Test behavior with malformed setup.py (syntax error)."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter"
    extras_require={  # Missing comma above
        "dev": ["pytest"],
    },
)
"""
        )

        # Should return empty set and not raise exception
        extras = _extras_from_setup(setup_py)
        assert extras == set()

    def test_setup_with_qualified_name(self, temp_adapter_dir):
        """Test parsing setup.py where setup is called with qualified name."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
import setuptools

setuptools.setup(
    name="test_adapter",
    extras_require={
        "azure": ["azure-core"],
    },
)
"""
        )

        extras = _extras_from_setup(setup_py)
        assert extras == {"azure"}

    def test_setup_with_alias(self, temp_adapter_dir):
        """Test parsing setup.py where setup is imported with alias."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup as setup_package

setup_package(
    name="test_adapter",
    extras_require={
        "test": ["pytest"],
    },
)
"""
        )

        # This test verifies current behavior - aliases are NOT detected
        # The function only looks for literal "setup" name or "setup" attribute
        extras = _extras_from_setup(setup_py)
        # Since "setup_package" is not recognized, should return empty set
        assert extras == set()

    def test_unicode_content(self, temp_adapter_dir):
        """Test parsing setup.py with unicode characters."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    description="Тестовое описание",  # Cyrillic characters
    extras_require={
        "dev": ["pytest"],
    },
)
""",
            encoding="utf-8",
        )

        extras = _extras_from_setup(setup_py)
        assert extras == {"dev"}


class TestSelectAzureExtra:
    """Test select_azure_extra() function."""

    def test_select_azure_when_both_present(self, temp_adapter_dir):
        """Test that 'azure' is selected when both 'azure' and 'azuremonitor' are present."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "azure": ["azure-core"],
        "azuremonitor": ["azure-monitor-opentelemetry-exporter"],
    },
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra == "azure"

    def test_select_azuremonitor_when_only_present(self, temp_adapter_dir):
        """Test that 'azuremonitor' is selected when only it is present."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "azuremonitor": ["azure-monitor-opentelemetry-exporter"],
    },
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra == "azuremonitor"

    def test_select_azure_when_only_present(self, temp_adapter_dir):
        """Test that 'azure' is selected when only it is present."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "azure": ["azure-core"],
    },
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra == "azure"

    def test_return_none_when_no_azure_extras(self, temp_adapter_dir):
        """Test that None is returned when no azure-related extras are defined."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "dev": ["pytest"],
        "test": ["pytest-cov"],
    },
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra is None

    def test_return_none_when_no_extras_defined(self, temp_adapter_dir):
        """Test that None is returned when no extras_require is defined."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    install_requires=["requests"],
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra is None

    def test_return_none_when_setup_missing(self, temp_adapter_dir):
        """Test that None is returned when setup.py is missing."""
        extra = select_azure_extra(temp_adapter_dir)
        assert extra is None

    def test_return_none_when_setup_malformed(self, temp_adapter_dir):
        """Test that None is returned when setup.py is malformed."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter"
    extras_require={  # Missing comma
        "azure": ["azure-core"],
    },
)
"""
        )

        extra = select_azure_extra(temp_adapter_dir)
        assert extra is None

    def test_priority_order_with_both_extras(self, temp_adapter_dir):
        """Test that 'azure' has priority over 'azuremonitor' when both are present."""
        setup_py = temp_adapter_dir / "setup.py"
        setup_py.write_text(
            """
from setuptools import setup

setup(
    name="test_adapter",
    extras_require={
        "dev": ["pytest"],
        "azuremonitor": ["azure-monitor-opentelemetry-exporter"],
        "azure": ["azure-core"],
        "test": ["pytest-cov"],
    },
)
"""
        )

        # 'azure' should be selected because AZURE_EXTRA_ORDER = ("azure", "azuremonitor")
        extra = select_azure_extra(temp_adapter_dir)
        assert extra == "azure"
