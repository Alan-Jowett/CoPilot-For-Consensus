# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Draft diff provider abstraction layer.

This package provides an abstraction for fetching and representing draft diffs
from multiple sources (e.g., Datatracker, GitHub, local files) and in multiple
formats (e.g., HTML, Markdown, plain text).
"""

from .models import DraftDiff
from .provider import DraftDiffProvider
from .datatracker_provider import DatatrackerDiffProvider
from .mock_provider import MockDiffProvider
from .factory import DiffProviderFactory, create_diff_provider

__all__ = [
    "DraftDiff",
    "DraftDiffProvider",
    "DatatrackerDiffProvider",
    "MockDiffProvider",
    "DiffProviderFactory",
    "create_diff_provider",
]
