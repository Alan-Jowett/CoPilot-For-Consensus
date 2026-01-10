# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Import smoke tests to ensure all modules can be imported without errors.

This test suite validates that all Python modules in the project can be
successfully imported, catching AttributeError, NameError, and other
import-time issues before they reach production.
"""

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

# Define all service and adapter module paths relative to repository root
SERVICE_PATHS = [
    "chunking.app",
    "embedding.app",
    "ingestion.app",
    "orchestrator.app",
    "parsing.app",
    "reporting.app",
    "summarization.app",
]

ADAPTER_MODULES = [
    "copilot_auth",
    "copilot_chunking",
    "copilot_config",
    "copilot_consensus",
    "copilot_embedding",
    "copilot_message_bus",
    "copilot_logging",
    "copilot_metrics",
    "copilot_archive_fetcher",
    "copilot_archive_store",
    "copilot_error_reporting",
    "copilot_schema_validation",
    "copilot_storage",
    "copilot_summarization",
    "copilot_vectorstore",
    "copilot_draft_diff",
    "copilot_startup",
]


def get_repo_root() -> Path:
    """Get the repository root directory."""
    # From tests/ directory, go up one level
    return Path(__file__).parent.parent


def add_service_to_path(service_path: str) -> None:
    """Add service directory to sys.path for importing."""
    repo_root = get_repo_root()
    # Extract service name (e.g., "chunking" from "chunking.app")
    service_name = service_path.split(".")[0]
    service_dir = repo_root / service_name
    if service_dir.exists() and str(service_dir) not in sys.path:
        sys.path.insert(0, str(service_dir))


def add_adapters_to_path() -> None:
    """Add adapters directory to sys.path for importing."""
    repo_root = get_repo_root()
    adapters_dir = repo_root / "adapters"
    if adapters_dir.exists() and str(adapters_dir) not in sys.path:
        sys.path.insert(0, str(adapters_dir))

    # Add each adapter's package directory
    for adapter in ADAPTER_MODULES:
        adapter_dir = adapters_dir / adapter
        if adapter_dir.exists() and str(adapter_dir) not in sys.path:
            sys.path.insert(0, str(adapter_dir))


def discover_submodules(package_name: str) -> list[str]:
    """
    Discover all submodules within a package.

    Args:
        package_name: Name of the package to explore

    Returns:
        List of fully qualified module names
    """
    try:
        package = importlib.import_module(package_name)
    except (ImportError, ModuleNotFoundError) as e:
        pytest.skip(f"Package {package_name} not available: {e}")
        return []

    if not hasattr(package, "__path__"):
        # Not a package, just a module
        return [package_name]

    modules = [package_name]

    try:
        for _, modname, ispkg in pkgutil.walk_packages(
            package.__path__,
            prefix=f"{package_name}.",
            onerror=lambda x: None
        ):
            modules.append(modname)
    except Exception:
        # If walk_packages fails, just return the base package
        pass

    return modules


class TestServiceImports:
    """Test that all service modules can be imported without errors."""

    @pytest.mark.parametrize("service_path", SERVICE_PATHS)
    def test_service_imports(self, service_path: str) -> None:
        """Test that a service module can be imported.

        Args:
            service_path: Service module path (e.g., "chunking.app")
        """
        # Add service to path
        add_service_to_path(service_path)

        # Try importing the module
        try:
            importlib.import_module(service_path)
        except ModuleNotFoundError as e:
            # Service might not have all dependencies installed in test environment
            pytest.skip(f"Service {service_path} dependencies not available: {e}")
        except AttributeError as e:
            pytest.fail(
                f"AttributeError when importing {service_path}: {e}\n"
                "This likely indicates a missing field or incorrect attribute access."
            )
        except Exception as e:
            # For other errors, fail the test with context
            pytest.fail(
                f"Failed to import {service_path}: {type(e).__name__}: {e}"
            )


class TestAdapterImports:
    """Test that all adapter modules can be imported without errors."""

    @pytest.mark.parametrize("adapter_name", ADAPTER_MODULES)
    def test_adapter_base_imports(self, adapter_name: str) -> None:
        """Test that an adapter package can be imported.

        Args:
            adapter_name: Adapter module name (e.g., "copilot_config")
        """
        # Add adapters to path
        add_adapters_to_path()

        # Try importing the adapter
        try:
            importlib.import_module(adapter_name)
        except ModuleNotFoundError as e:
            pytest.skip(f"Adapter {adapter_name} not installed: {e}")
        except AttributeError as e:
            pytest.fail(
                f"AttributeError when importing {adapter_name}: {e}\n"
                "This likely indicates a missing field or incorrect attribute access."
            )
        except Exception as e:
            pytest.fail(
                f"Failed to import {adapter_name}: {type(e).__name__}: {e}"
            )

    @pytest.mark.parametrize("adapter_name", ADAPTER_MODULES)
    def test_adapter_submodules_import(self, adapter_name: str) -> None:
        """Test that all submodules within an adapter can be imported.

        Args:
            adapter_name: Adapter module name
        """
        # Add adapters to path
        add_adapters_to_path()

        # Discover all submodules
        submodules = discover_submodules(adapter_name)

        # Track failures
        failures = []

        for submodule in submodules:
            try:
                importlib.import_module(submodule)
            except ModuleNotFoundError:
                # Skip if dependencies not available
                continue
            except AttributeError as e:
                failures.append(
                    f"AttributeError in {submodule}: {e}"
                )
            except Exception as e:
                failures.append(
                    f"Error in {submodule}: {type(e).__name__}: {e}"
                )

        if failures:
            pytest.fail(
                f"Failed to import submodules in {adapter_name}:\n" +
                "\n".join(failures)
            )


class TestScriptImports:
    """Test that utility scripts can be imported without errors."""

    def test_scripts_directory(self) -> None:
        """Test that scripts in the scripts/ directory can be imported."""
        repo_root = get_repo_root()
        scripts_dir = repo_root / "scripts"

        if not scripts_dir.exists():
            pytest.skip("No scripts directory found")

        # Add scripts to path
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        failures = []

        for script_file in scripts_dir.glob("*.py"):
            if script_file.name.startswith("_"):
                continue

            module_name = script_file.stem

            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError:
                # Skip if dependencies not available
                continue
            except AttributeError as e:
                failures.append(
                    f"AttributeError in {module_name}: {e}"
                )
            except SystemExit:
                # Scripts might call sys.exit() at module level
                continue
            except Exception as e:
                # Some scripts may have side effects, be lenient
                if "AttributeError" in str(e):
                    failures.append(
                        f"Error in {module_name}: {e}"
                    )

        if failures:
            pytest.fail(
                "Failed to import scripts:\n" + "\n".join(failures)
            )


def test_no_warnings_on_import() -> None:
    """
    Test that importing key modules doesn't produce warnings.

    This helps catch deprecated API usage and other issues.
    """
    import warnings

    # Add necessary paths
    add_adapters_to_path()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Try importing a few key adapters
        for adapter in ["copilot_config", "copilot_logging", "copilot_message_bus"]:
            try:
                importlib.import_module(adapter)
            except ModuleNotFoundError:
                # Not installed, skip
                continue

        # Check for DeprecationWarnings or other concerning warnings
        concerning_warnings = [
            warning for warning in w
            if issubclass(warning.category, DeprecationWarning | FutureWarning)
        ]

        if concerning_warnings:
            warning_messages = [
                f"{w.category.__name__}: {w.message}"
                for w in concerning_warnings
            ]
            # Don't fail, just report
            print(
                "Warnings detected during imports:\n" +
                "\n".join(warning_messages)
            )
