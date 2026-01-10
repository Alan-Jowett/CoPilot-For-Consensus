# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Draft diff provider abstraction layer.

This package provides an abstraction for fetching and representing draft diffs
from multiple sources (e.g., Datatracker, GitHub, local files) and in multiple
formats (e.g., HTML, Markdown, plain text).
"""

from .factory import DiffProviderFactory, create_diff_provider
from .models import DraftDiff
from .provider import DraftDiffProvider

__all__ = [
    "DraftDiff",
    "DraftDiffProvider",
    "DiffProviderFactory",
    "create_diff_provider",
]
