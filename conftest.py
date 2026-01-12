# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Root conftest.py to ensure tests/ package is importable from all services."""

import sys
from pathlib import Path

# Add repo root to sys.path so tests.fixtures can be imported
_repo_root = Path(__file__).parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
