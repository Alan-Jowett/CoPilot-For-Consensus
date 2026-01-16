# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test configuration for copilot_auth.

These tests run the adapter in isolation without installing sibling adapters.
Add `adapters/copilot_config` to `sys.path` so generated typed config models are
importable as `copilot_config.generated.*`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


REPO_ROOT = Path(__file__).resolve().parents[3]
_add_path(REPO_ROOT / "adapters" / "copilot_config")
