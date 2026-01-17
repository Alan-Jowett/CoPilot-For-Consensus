# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Draft and RFC mention detection."""

import re


class DraftDetector:
    """Detects RFC and draft mentions in text."""

    DEFAULT_PATTERN = r'(draft-[a-z0-9-]+-\d+)|(RFC\s*\d+)|(rfc\d+)'

    def __init__(self, pattern: str | None = None):
        """Initialize draft detector.

        Args:
            pattern: Regex pattern for draft detection (uses default if None)
        """
        self.pattern = pattern or self.DEFAULT_PATTERN
        self.regex = re.compile(self.pattern, re.IGNORECASE)

    def detect(self, text: str) -> list[str]:
        """Detect RFC and draft mentions in text.

        Args:
            text: Text to search for draft mentions

        Returns:
            List of unique draft/RFC identifiers found
        """
        if not text:
            return []

        matches = self.regex.findall(text)

        # Flatten tuples and normalize
        drafts = []
        for match in matches:
            # Handle tuple groups from regex
            if isinstance(match, tuple):
                for group in match:
                    if group:
                        drafts.append(self._normalize_draft(group))
            else:
                drafts.append(self._normalize_draft(match))

        # Remove duplicates while preserving order
        seen = set()
        unique_drafts = []
        for draft in drafts:
            if draft not in seen:
                seen.add(draft)
                unique_drafts.append(draft)

        return unique_drafts

    def _normalize_draft(self, draft_str: str) -> str:
        """Normalize draft/RFC format.

        Args:
            draft_str: Raw draft/RFC string

        Returns:
            Normalized draft/RFC identifier
        """
        # Normalize RFC format to "RFC XXXX"
        if draft_str.lower().startswith('rfc'):
            # Extract just the number
            match = re.search(r'\d+', draft_str)
            if match:
                return f'RFC {match.group()}'

        # Return draft identifiers as-is (already in standard format)
        return draft_str
