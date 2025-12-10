# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for mock diff provider."""

import pytest
from draft_diff.mock_provider import MockDiffProvider
from draft_diff.models import DraftDiff


class TestMockDiffProvider:
    """Tests for MockDiffProvider."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        provider = MockDiffProvider()
        
        assert provider.mock_diffs == {}
        assert provider.default_format == "text"
    
    def test_initialization_with_format(self):
        """Test initialization with custom format."""
        provider = MockDiffProvider(default_format="html")
        
        assert provider.default_format == "html"
    
    def test_getdiff_auto_generated_text(self):
        """Test auto-generated text diff."""
        provider = MockDiffProvider(default_format="text")
        
        diff = provider.getdiff("draft-test", "01", "02")
        
        assert isinstance(diff, DraftDiff)
        assert diff.draft_name == "draft-test"
        assert diff.version_a == "01"
        assert diff.version_b == "02"
        assert diff.format == "text"
        assert diff.source == "mock"
        assert "draft-test" in diff.content
        assert "01" in diff.content
        assert "02" in diff.content
        assert diff.url == "mock://draft-test/01..02"
        assert diff.metadata["mock"] is True
        assert diff.metadata["generated"] is True
    
    def test_getdiff_auto_generated_html(self):
        """Test auto-generated HTML diff."""
        provider = MockDiffProvider(default_format="html")
        
        diff = provider.getdiff("draft-ietf-quic", "00", "01")
        
        assert diff.format == "html"
        assert "<html>" in diff.content
        assert "</html>" in diff.content
        assert "draft-ietf-quic" in diff.content
    
    def test_getdiff_auto_generated_markdown(self):
        """Test auto-generated Markdown diff."""
        provider = MockDiffProvider(default_format="markdown")
        
        diff = provider.getdiff("draft-example", "10", "11")
        
        assert diff.format == "markdown"
        assert "#" in diff.content
        assert "draft-example" in diff.content
    
    def test_getdiff_with_predefined_mock(self):
        """Test getdiff with predefined mock diff."""
        predefined = DraftDiff(
            draft_name="draft-custom",
            version_a="01",
            version_b="02",
            format="text",
            content="Custom predefined content",
            source="mock",
            url="custom://url"
        )
        
        mock_diffs = {
            ("draft-custom", "01", "02"): predefined
        }
        
        provider = MockDiffProvider(mock_diffs=mock_diffs)
        diff = provider.getdiff("draft-custom", "01", "02")
        
        assert diff == predefined
        assert diff.content == "Custom predefined content"
    
    def test_add_mock_diff(self):
        """Test adding a mock diff dynamically."""
        provider = MockDiffProvider()
        
        custom_diff = DraftDiff(
            draft_name="draft-dynamic",
            version_a="05",
            version_b="06",
            format="html",
            content="<p>Dynamic content</p>",
            source="mock"
        )
        
        provider.add_mock_diff("draft-dynamic", "05", "06", custom_diff)
        
        diff = provider.getdiff("draft-dynamic", "05", "06")
        assert diff == custom_diff
        assert diff.content == "<p>Dynamic content</p>"
    
    def test_getdiff_empty_draft_name(self):
        """Test that empty draft name raises ValueError."""
        provider = MockDiffProvider()
        
        with pytest.raises(ValueError, match="draft_name cannot be empty"):
            provider.getdiff("", "01", "02")
    
    def test_getdiff_empty_version_a(self):
        """Test that empty version_a raises ValueError."""
        provider = MockDiffProvider()
        
        with pytest.raises(ValueError, match="version_a and version_b must be provided"):
            provider.getdiff("draft-test", "", "02")
    
    def test_getdiff_empty_version_b(self):
        """Test that empty version_b raises ValueError."""
        provider = MockDiffProvider()
        
        with pytest.raises(ValueError, match="version_a and version_b must be provided"):
            provider.getdiff("draft-test", "01", "")
