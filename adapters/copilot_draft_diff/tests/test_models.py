# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for draft diff models."""

from copilot_draft_diff.models import DraftDiff


class TestDraftDiff:
    """Tests for DraftDiff model."""

    def test_basic_initialization(self):
        """Test basic DraftDiff initialization."""
        diff = DraftDiff(
            draft_name="draft-ietf-quic-transport",
            version_a="01",
            version_b="02",
            format="text",
            content="Mock diff content",
            source="mock"
        )

        assert diff.draft_name == "draft-ietf-quic-transport"
        assert diff.version_a == "01"
        assert diff.version_b == "02"
        assert diff.format == "text"
        assert diff.content == "Mock diff content"
        assert diff.source == "mock"
        assert diff.url is None
        assert diff.metadata is None

    def test_initialization_with_optional_fields(self):
        """Test DraftDiff initialization with optional fields."""
        metadata = {"lines_added": 10, "lines_removed": 5}
        diff = DraftDiff(
            draft_name="draft-ietf-quic-transport",
            version_a="01",
            version_b="02",
            format="html",
            content="<html>Mock diff</html>",
            source="datatracker",
            url="https://datatracker.ietf.org/doc/draft-ietf-quic-transport/diff/",
            metadata=metadata
        )

        assert diff.url == "https://datatracker.ietf.org/doc/draft-ietf-quic-transport/diff/"
        assert diff.metadata == metadata
        assert diff.metadata["lines_added"] == 10

    def test_to_dict(self):
        """Test conversion to dictionary."""
        diff = DraftDiff(
            draft_name="draft-test",
            version_a="00",
            version_b="01",
            format="markdown",
            content="# Changes",
            source="mock",
            url="mock://test",
            metadata={"test": True}
        )

        result = diff.to_dict()

        assert isinstance(result, dict)
        assert result["draft_name"] == "draft-test"
        assert result["version_a"] == "00"
        assert result["version_b"] == "01"
        assert result["format"] == "markdown"
        assert result["content"] == "# Changes"
        assert result["source"] == "mock"
        assert result["url"] == "mock://test"
        assert result["metadata"]["test"] is True
