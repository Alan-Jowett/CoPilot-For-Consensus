#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors
"""
Centralized script to install adapters in dependency order.
Used by both GitHub Actions CI and Docker builds.

Usage:
    # Install all adapters:
    python adapters/scripts/install_adapters.py

    # Install specific adapters only:
    python adapters/scripts/install_adapters.py copilot_config copilot_storage copilot_message_bus

    # Install with --no-dev flag (no dev dependencies):
    python adapters/scripts/install_adapters.py --no-dev
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path

# Dependency order - install these first, then others
# copilot_config MUST be first - it has no dependencies and many adapters depend on it
# copilot_schema_validation and copilot_vectorstore have no adapter dependencies
# Everything else depends on copilot_config
PRIORITY_ADAPTERS = [
    "copilot_config",
    "copilot_schema_validation",
    "copilot_vectorstore",
    "copilot_archive_fetcher",
    "copilot_archive_store",
    "copilot_draft_diff",
    "copilot_logging",
    "copilot_storage",
    "copilot_message_bus",
    "copilot_secrets",
]

# Dependency map - what each adapter depends on
ADAPTER_DEPENDENCIES = {
    "copilot_config": [],  # Config has no dependencies - must install first!
    "copilot_schema_validation": [],  # Schema validation has no dependencies
    "copilot_event_retry": [],  # Event retry has no adapter dependencies (stdlib only)
    "copilot_storage": [
        "copilot_config",
        "copilot_schema_validation",
    ],  # Storage depends on copilot-config and schema-validation for tests
    "copilot_message_bus": ["copilot_config", "copilot_schema_validation"],  # Message-bus depends on both
    "copilot_secrets": ["copilot_logging"],  # Secrets depends on logging
    "copilot_chunking": ["copilot_config", "copilot_schema_validation"],  # Chunking depends on both
    "copilot_logging": ["copilot_config"],  # Logging depends on copilot-config
    "copilot_metrics": ["copilot_config"],  # Metrics depends on copilot-config
    "copilot_error_reporting": ["copilot_config"],  # Error reporting depends on copilot-config
    "copilot_embedding": ["copilot_config"],  # Embedding depends on copilot-config
    "copilot_vectorstore": ["copilot_config"],  # Vectorstore depends on copilot-config (for tests)
    "copilot_summarization": ["copilot_config"],  # Summarization depends on copilot-config
    "copilot_archive_fetcher": [],  # Archive fetcher has no adapter dependencies
    "copilot_archive_store": [],  # Archive store has no adapter dependencies
    "copilot_auth": ["copilot_config", "copilot_logging"],  # Auth depends on config and logging
    "copilot_draft_diff": ["copilot_config"],  # Draft diff depends on copilot-config
    "copilot_consensus": ["copilot_config"],  # Consensus depends on copilot-config
    "copilot_startup": [
        "copilot_config",
        "copilot_schema_validation",
        "copilot_message_bus",
        "copilot_metrics",
        "copilot_storage",
    ],  # Startup depends on config, schema-validation, message-bus, metrics, and storage
}


def get_adapters_dir():
    """Get the adapters directory relative to this script."""
    # Script is at adapters/scripts/install_adapters.py
    script_dir = Path(__file__).parent.parent  # Navigate to adapters/
    if not script_dir.exists():
        raise FileNotFoundError(f"Adapters directory not found: {script_dir}")
    return script_dir


def get_all_adapter_names():
    """Get all available adapter names."""
    adapters_dir = get_adapters_dir()
    all_adapters = []
    for item in adapters_dir.iterdir():
        if item.is_dir() and ((item / "setup.py").exists() or (item / "pyproject.toml").exists()):
            all_adapters.append(item.name)
    return all_adapters


def get_adapter_dirs():
    """Get all valid adapter directories, sorted by dependency order."""
    adapters_dir = get_adapters_dir()
    all_adapters = get_all_adapter_names()

    # Sort with priority adapters first, then alphabetically
    sorted_adapters = []
    for adapter in PRIORITY_ADAPTERS:
        if adapter in all_adapters:
            sorted_adapters.append(adapter)
            all_adapters.remove(adapter)
    sorted_adapters.extend(sorted(all_adapters))

    return [adapters_dir / adapter for adapter in sorted_adapters]


def resolve_dependencies(requested_adapters):
    """Resolve all dependencies for requested adapters in install order.

    Args:
        requested_adapters: List of adapter names to install

    Returns:
        List of adapter names in dependency order
    """
    resolved = []
    visited = set()

    def visit(adapter):
        if adapter in visited:
            return
        visited.add(adapter)

        # Visit dependencies first
        for dep in ADAPTER_DEPENDENCIES.get(adapter, []):
            visit(dep)

        if adapter not in resolved:
            resolved.append(adapter)

    # Visit each requested adapter
    for adapter in requested_adapters:
        visit(adapter)

    # Sort resolved list by priority order
    priority_sorted = []
    for adapter in PRIORITY_ADAPTERS:
        if adapter in resolved:
            priority_sorted.append(adapter)
            resolved.remove(adapter)
    priority_sorted.extend(sorted(resolved))

    return priority_sorted


AZURE_EXTRA_ORDER = ("azure", "azuremonitor")


def _is_setup_call(node: ast.expr) -> bool:
    """Check if node is a call to setup() (handles both simple and qualified names).

    Returns True for:
    - setup(...) - simple name
    - setuptools.setup(...) - qualified name
    """
    if isinstance(node, ast.Name) and node.id == "setup":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "setup":
        return True
    return False


def _extras_from_setup(setup_path: Path) -> set[str]:
    """Extract extras keys from setup.py (best-effort).

    Returns an empty set if:
    - setup.py doesn't exist
    - setup.py cannot be parsed
    - setup.py has no setup() call
    - setup.py setup() call has no extras_require
    """
    if not setup_path.exists():
        return set()

    try:
        tree = ast.parse(setup_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_setup_call(node.func):
                for kw in node.keywords:
                    if kw.arg == "extras_require":
                        extras = ast.literal_eval(kw.value)
                        if isinstance(extras, dict):
                            return set(extras.keys())
    except Exception as e:
        # Log parse failures for debugging without breaking the install flow
        print(f"  -> Warning: Failed to parse {setup_path.name}: {e}", file=sys.stderr)

    # Return empty set if no extras_require found or parsing failed
    return set()


def select_azure_extra(adapter_path: Path) -> str | None:
    """Return the azure-related extra to use if defined for this adapter."""
    extras = _extras_from_setup(adapter_path / "setup.py")
    for candidate in AZURE_EXTRA_ORDER:
        if candidate in extras:
            return candidate
    return None


def install_adapter(adapter_path):
    """Install a single adapter in editable mode, using azure extras only when defined."""
    print(f"Installing adapter: {adapter_path.name}")

    azure_extra = select_azure_extra(adapter_path)
    target = f"{str(adapter_path)}[{azure_extra}]" if azure_extra else str(adapter_path)

    if not azure_extra:
        print("  -> No azure extras declared; installing without extras")
    else:
        print(f"  -> Installing with [{azure_extra}] extras")

    result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", target], capture_output=False)
    if result.returncode != 0:
        print(f"ERROR: Failed to install {adapter_path.name}", file=sys.stderr)
        return False
    return True


def main():
    """Install all adapters or specific adapters in dependency order."""
    parser = argparse.ArgumentParser(
        description="Install adapters in dependency order",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install all adapters
  python install_adapters.py

  # Install specific adapters (with dependencies)
  python install_adapters.py copilot_config copilot_storage copilot_message_bus

  # Install without dev dependencies
  python install_adapters.py --no-dev
        """,
    )
    parser.add_argument("adapters", nargs="*", help="Specific adapters to install (installs all if not specified)")
    parser.add_argument(
        "--no-dev", action="store_true", help="Skip development dependencies (ignored, for compatibility)"
    )

    args = parser.parse_args()

    adapters_dir = get_adapters_dir()

    # Determine which adapters to install
    if args.adapters:
        # User specified adapters - resolve dependencies
        requested = args.adapters
        print(f"Requested adapters: {', '.join(requested)}")

        # Resolve dependencies
        to_install = resolve_dependencies(requested)
        print(f"Installing with dependencies: {', '.join(to_install)}")

        # Convert to paths
        adapter_paths = [adapters_dir / adapter for adapter in to_install]

        # Verify all exist
        missing = [p for p in adapter_paths if not p.exists()]
        if missing:
            print(f"ERROR: Adapters not found: {', '.join(p.name for p in missing)}", file=sys.stderr)
            return 1
    else:
        # Install all adapters
        adapter_paths = get_adapter_dirs()
        print(f"Installing all {len(adapter_paths)} adapters")

    if not adapter_paths:
        print("WARNING: No adapters found to install")
        return 0

    print(f"Install order: {', '.join(a.name for a in adapter_paths)}")

    failed = []
    for adapter_path in adapter_paths:
        if not install_adapter(adapter_path):
            failed.append(adapter_path.name)

    if failed:
        print(f"\nERROR: Failed to install adapters: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"\nSuccessfully installed {len(adapter_paths)} adapters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
