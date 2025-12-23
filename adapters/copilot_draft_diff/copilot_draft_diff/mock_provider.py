# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Mock diff provider implementation for testing."""

from typing import Optional, Dict, Tuple
from .provider import DraftDiffProvider
from .models import DraftDiff


class MockDiffProvider(DraftDiffProvider):
    """Mock provider for testing draft diff functionality.

    This provider returns synthetic diff data for testing purposes.
    It can be configured with predefined diffs or will generate simple
    mock diffs based on the input parameters.

    Attributes:
        mock_diffs: Dictionary mapping (draft_name, version_a, version_b) tuples
                   to DraftDiff objects for predefined responses
        default_format: Default format for generated mock diffs
    """

    def __init__(self, mock_diffs: Optional[Dict[Tuple[str, str, str], DraftDiff]] = None, default_format: str = "text"):
        """Initialize mock diff provider.

        Args:
            mock_diffs: Optional dictionary of predefined mock diffs
                       Keys should be (draft_name, version_a, version_b) tuples
                       Values should be DraftDiff objects
            default_format: Default format for auto-generated mock diffs
        """
        self.mock_diffs = mock_diffs or {}
        self.default_format = default_format

    def getdiff(self, draft_name: str, version_a: str, version_b: str) -> DraftDiff:
        """Fetch a mock diff between two versions of a draft.

        Args:
            draft_name: Name of the draft (e.g., "draft-ietf-quic-transport")
            version_a: Version A identifier (e.g., "01", "02")
            version_b: Version B identifier (e.g., "02", "03")

        Returns:
            DraftDiff object containing mock diff content and metadata

        Raises:
            ValueError: If draft_name is empty or versions are invalid
        """
        # Validate inputs
        if not draft_name:
            raise ValueError("draft_name cannot be empty")
        if not version_a or not version_b:
            raise ValueError("version_a and version_b must be provided")

        # Check if we have a predefined mock diff
        key = (draft_name, version_a, version_b)
        if key in self.mock_diffs:
            return self.mock_diffs[key]

        # Generate a simple mock diff
        content = self._generate_mock_diff_content(draft_name, version_a, version_b)

        return DraftDiff(
            draft_name=draft_name,
            version_a=version_a,
            version_b=version_b,
            format=self.default_format,
            content=content,
            source="mock",
            url=f"mock://{draft_name}/{version_a}..{version_b}",
            metadata={
                "mock": True,
                "generated": True,
            }
        )

    def _generate_mock_diff_content(self, draft_name: str, version_a: str, version_b: str) -> str:
        """Generate mock diff content.

        Args:
            draft_name: Name of the draft
            version_a: Version A identifier
            version_b: Version B identifier

        Returns:
            Mock diff content as a string
        """
        if self.default_format == "html":
            return f"""<html>
<head><title>Diff: {draft_name} {version_a} to {version_b}</title></head>
<body>
<h1>Mock Diff: {draft_name}</h1>
<p>Changes from version {version_a} to {version_b}</p>
<div class="diff">
<span class="removed">- Old content from version {version_a}</span>
<span class="added">+ New content in version {version_b}</span>
</div>
</body>
</html>"""
        elif self.default_format == "markdown":
            return f"""# Mock Diff: {draft_name}

Changes from version {version_a} to {version_b}

## Changes
```diff
- Old content from version {version_a}
+ New content in version {version_b}
```
"""
        else:  # text format
            return f"""Mock diff for {draft_name}
Version {version_a} -> {version_b}

- Old content from version {version_a}
+ New content in version {version_b}
"""

    def add_mock_diff(self, draft_name: str, version_a: str, version_b: str, diff: DraftDiff) -> None:
        """Add a predefined mock diff.

        Args:
            draft_name: Name of the draft
            version_a: Version A identifier
            version_b: Version B identifier
            diff: DraftDiff object to return for these parameters
        """
        key = (draft_name, version_a, version_b)
        self.mock_diffs[key] = diff
