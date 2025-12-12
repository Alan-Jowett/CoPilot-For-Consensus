# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

#!/usr/bin/env python3
"""
Centralized script to install adapters in dependency order.
Used by both GitHub Actions CI and Docker builds.

Usage:
    python adapters/scripts/install_adapters.py
    or from within adapters: python scripts/install_adapters.py
"""

import sys
import subprocess
from pathlib import Path

# Dependency order - install these first, then others
# Storage has no dependencies
# Schema-validation depends on storage
# Events depends on schema-validation
# Config has no dependencies
# Everything else can come after
PRIORITY_ADAPTERS = [
    "copilot_storage",
    "copilot_schema_validation",
    "copilot_events",
    "copilot_config",
    "copilot_summarization",
]

def get_adapters_dir():
    """Get the adapters directory relative to this script."""
    # Script is at adapters/scripts/install_adapters.py
    script_dir = Path(__file__).parent.parent  # Navigate to adapters/
    if not script_dir.exists():
        raise FileNotFoundError(f"Adapters directory not found: {script_dir}")
    return script_dir

def get_adapter_dirs():
    """Get all valid adapter directories, sorted by dependency order."""
    adapters_dir = get_adapters_dir()
    
    # Get all directories that contain setup.py or pyproject.toml
    all_adapters = []
    for item in adapters_dir.iterdir():
        if item.is_dir() and ((item / "setup.py").exists() or (item / "pyproject.toml").exists()):
            all_adapters.append(item.name)
    
    # Sort with priority adapters first, then alphabetically
    sorted_adapters = []
    for adapter in PRIORITY_ADAPTERS:
        if adapter in all_adapters:
            sorted_adapters.append(adapter)
            all_adapters.remove(adapter)
    sorted_adapters.extend(sorted(all_adapters))
    
    return [adapters_dir / adapter for adapter in sorted_adapters]

def install_adapter(adapter_path):
    """Install a single adapter in editable mode."""
    print(f"Installing adapter: {adapter_path.name}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(adapter_path)],
        capture_output=False
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to install {adapter_path.name}", file=sys.stderr)
        return False
    return True

def main():
    """Install all adapters in dependency order."""
    adapter_dirs = get_adapter_dirs()
    if not adapter_dirs:
        print("WARNING: No adapters found to install")
        return 0
    
    print(f"Installing {len(adapter_dirs)} adapters in dependency order...")
    print(f"Order: {', '.join(a.name for a in adapter_dirs)}")
    
    failed = []
    for adapter_path in adapter_dirs:
        if not install_adapter(adapter_path):
            failed.append(adapter_path.name)
    
    if failed:
        print(f"\nERROR: Failed to install adapters: {', '.join(failed)}", file=sys.stderr)
        return 1
    
    print(f"\nSuccessfully installed all {len(adapter_dirs)} adapters")
    return 0

if __name__ == "__main__":
    sys.exit(main())
