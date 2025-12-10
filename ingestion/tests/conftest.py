# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures."""
import sys
from pathlib import Path

# Add parent directory to path so tests can import app module
sys.path.insert(0, str(Path(__file__).parent.parent))
