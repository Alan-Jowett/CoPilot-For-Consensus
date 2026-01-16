# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest config for copilot_consensus adapter tests.

These adapter tests are often executed from within the adapter folder.
In that mode, sibling adapters (like `copilot_config`) are not
automatically on `sys.path`.

This file adds the relevant sibling adapter roots so imports work
consistently in local and CI runs.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_adapter_to_syspath(repo_root: Path, adapter_name: str) -> None:
    adapter_path = repo_root / "adapters" / adapter_name
    if adapter_path.exists() and str(adapter_path) not in sys.path:
        sys.path.insert(0, str(adapter_path))


def pytest_configure() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    _add_adapter_to_syspath(repo_root, "copilot_config")
