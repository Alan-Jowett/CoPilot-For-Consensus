# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration for copilot_archive_store.

This adapter depends on the shared `copilot_config` adapter for generated typed
configuration models. When running this adapter's tests in isolation, the
`copilot_config` package is not installed into the environment, so we add the
adapter project root to `sys.path`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_adapter_on_path(adapter_dir_name: str) -> None:
    adapters_dir = Path(__file__).resolve().parents[2]
    adapter_root = adapters_dir / adapter_dir_name
    if adapter_root.exists():
        sys.path.insert(0, str(adapter_root))


_ensure_adapter_on_path("copilot_config")
