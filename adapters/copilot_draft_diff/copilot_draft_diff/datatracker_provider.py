# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Datatracker diff provider implementation."""

from .models import DraftDiff
from .provider import DraftDiffProvider


class DatatrackerDiffProvider(DraftDiffProvider):
    """Provider for fetching draft diffs from IETF Datatracker.

    This is the default backend for fetching diffs from the official
    IETF Datatracker service at https://datatracker.ietf.org/

    Attributes:
        base_url: Base URL for the Datatracker service
        diff_format: Default format for diffs (html, text)
    """

    def __init__(self, base_url: str = "https://datatracker.ietf.org", diff_format: str = "html"):
        """Initialize Datatracker diff provider.

        Args:
            base_url: Base URL for Datatracker service
            diff_format: Default format for diffs (html, text)
        """
        self.base_url = base_url.rstrip("/")
        self.diff_format = diff_format

    def getdiff(self, draft_name: str, version_a: str, version_b: str) -> DraftDiff:
        """Fetch a diff between two versions of a draft from Datatracker.

        Args:
            draft_name: Name of the draft (e.g., "draft-ietf-quic-transport")
            version_a: Version A identifier (e.g., "01", "02")
            version_b: Version B identifier (e.g., "02", "03")

        Returns:
            DraftDiff object containing the diff content and metadata

        Raises:
            ValueError: If draft_name is invalid or versions don't exist
            ConnectionError: If unable to fetch diff from Datatracker
            NotImplementedError: As this is a stub implementation
        """
        # TODO: Implement actual HTTP request to fetch diff from Datatracker
        # This is a stub implementation for now
        # Typical URL format: https://www.ietf.org/rfcdiff?url1=draft-name-01&url2=draft-name-02
        raise NotImplementedError(
            "DatatrackerDiffProvider.getdiff is not yet fully implemented. "
            "This requires HTTP client integration to fetch diffs from "
            f"{self.base_url}. Use MockDiffProvider for testing."
        )
