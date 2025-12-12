#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors
"""
Helper script to install extra pip packages for adapters.
Used by GitHub Actions CI workflows.

Usage:
    python install_extras.py '["package1", "package2"]'
"""

import sys
import subprocess
import json

def install_packages(packages):
    """Install a list of pip packages."""
    if not packages:
        return True
    
    for package in packages:
        if not package:
            continue
        print(f"Installing extra package: {package}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=False
        )
        if result.returncode != 0:
            print(f"ERROR: Failed to install {package}", file=sys.stderr)
            return False
    return True

def main():
    """Install extra packages passed as JSON array arguments."""
    if len(sys.argv) < 2:
        print("No packages to install")
        return 0
    
    try:
        packages = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON: {sys.argv[1]}", file=sys.stderr)
        return 1
    
    if not install_packages(packages):
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
