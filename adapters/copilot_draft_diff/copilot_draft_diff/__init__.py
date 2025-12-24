# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Draft diff provider abstraction layer.

This package provides an abstraction for fetching and representing draft diffs
from multiple sources (e.g., Datatracker, GitHub, local files) and in multiple
formats (e.g., HTML, Markdown, plain text).
"""

from .datatracker_provider import DatatrackerDiffProvider
from .factory import DiffProviderFactory, create_diff_provider
from .mock_provider import MockDiffProvider
from .models import DraftDiff
from .provider import DraftDiffProvider

__all__ = [
    "DraftDiff",
    "DraftDiffProvider",
    "DatatrackerDiffProvider",
    "MockDiffProvider",
    "DiffProviderFactory",
    "create_diff_provider",
]
