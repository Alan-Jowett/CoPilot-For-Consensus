# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures."""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Mock pymongo before any imports that might use it
# This prevents the SDK from trying to connect to MongoDB during tests
if "pymongo" not in sys.modules:
    sys.modules["pymongo"] = types.SimpleNamespace(MongoClient=MagicMock())

# Add parent directory to path so tests can import app module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add repo root + adapter project roots so tests can import shared adapters
# (e.g., copilot_config, copilot_logging, copilot_archive_fetcher).
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

adapters_dir = repo_root / "adapters"
if adapters_dir.is_dir():
    for adapter_root in sorted(adapters_dir.iterdir()):
        if not adapter_root.is_dir():
            continue
        sys.path.insert(0, str(adapter_root))
