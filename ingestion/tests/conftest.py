# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures."""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import types

# Mock pymongo before any imports that might use it
# This prevents the Adapter from trying to connect to MongoDB during tests
if "pymongo" not in sys.modules:
    sys.modules["pymongo"] = types.SimpleNamespace(MongoClient=MagicMock())

# Add parent directory to path so tests can import app module
sys.path.insert(0, str(Path(__file__).parent.parent))
