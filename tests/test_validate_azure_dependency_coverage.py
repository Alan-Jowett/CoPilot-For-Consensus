# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure dependency coverage validation script."""

from __future__ import annotations

import runpy
from pathlib import Path


def test_validate_azure_dependency_coverage_has_no_errors():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "validate_azure_dependency_coverage.py"

    script_globals = runpy.run_path(str(script_path))
    validate_repo = script_globals["validate_repo"]

    errors = validate_repo(repo_root)
    assert errors == [], "\n" + "\n".join(errors)
