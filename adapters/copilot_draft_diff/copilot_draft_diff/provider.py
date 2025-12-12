# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract base class for draft diff providers."""

from abc import ABC, abstractmethod
from .models import DraftDiff


class DraftDiffProvider(ABC):
    """Abstract base class for providers that fetch draft diffs.
    
    Subclasses must implement the getdiff method to fetch diffs from
    their specific source (e.g., Datatracker, GitHub, local files).
    """
    
    @abstractmethod
    def getdiff(self, draft_name: str, version_a: str, version_b: str) -> DraftDiff:
        """Fetch a diff between two versions of a draft.
        
        Args:
            draft_name: Name of the draft (e.g., "draft-ietf-quic-transport")
            version_a: Version A identifier (e.g., "01", "02")
            version_b: Version B identifier (e.g., "02", "03")
            
        Returns:
            DraftDiff object containing the diff content and metadata
            
        Raises:
            ValueError: If draft_name is invalid or versions don't exist
            ConnectionError: If unable to fetch diff from source
            NotImplementedError: If the provider doesn't support the operation
        """
        pass
