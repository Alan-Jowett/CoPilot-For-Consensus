# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for datatracker diff provider."""

import pytest
from copilot_draft_diff.datatracker_provider import DatatrackerDiffProvider


class TestDatatrackerDiffProvider:
    """Tests for DatatrackerDiffProvider."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        provider = DatatrackerDiffProvider()
        
        assert provider.base_url == "https://datatracker.ietf.org"
        assert provider.format == "html"
    
    def test_initialization_custom_url(self):
        """Test initialization with custom URL."""
        provider = DatatrackerDiffProvider(base_url="https://custom.example.com")
        
        assert provider.base_url == "https://custom.example.com"
    
    def test_initialization_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL."""
        provider = DatatrackerDiffProvider(base_url="https://example.com/")
        
        assert provider.base_url == "https://example.com"
    
    def test_initialization_custom_format(self):
        """Test initialization with custom format."""
        provider = DatatrackerDiffProvider(format="text")
        
        assert provider.format == "text"
    
    def test_getdiff_not_implemented(self):
        """Test that getdiff raises NotImplementedError as it's a stub."""
        provider = DatatrackerDiffProvider()
        
        with pytest.raises(NotImplementedError, match="not yet fully implemented"):
            provider.getdiff("draft-ietf-quic-transport", "01", "02")
    
    def test_getdiff_includes_url_hint(self):
        """Test that NotImplementedError includes URL information."""
        provider = DatatrackerDiffProvider(base_url="https://custom.example.com")
        
        with pytest.raises(NotImplementedError, match="https://custom.example.com"):
            provider.getdiff("draft-test", "00", "01")
