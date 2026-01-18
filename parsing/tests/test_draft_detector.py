# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for draft detector."""

from app.draft_detector import DraftDetector


class TestDraftDetector:
    """Tests for DraftDetector."""

    def test_detect_draft_mentions(self):
        """Test detecting draft mentions in text."""
        detector = DraftDetector()

        text = "See draft-ietf-quic-transport-34 for details."
        drafts = detector.detect(text)

        assert len(drafts) == 1
        assert "draft-ietf-quic-transport-34" in drafts

    def test_detect_rfc_mentions(self):
        """Test detecting RFC mentions."""
        detector = DraftDetector()

        text = "Refer to RFC 9000 and RFC9001 for specifications."
        drafts = detector.detect(text)

        assert len(drafts) == 2
        assert "RFC 9000" in drafts
        assert "RFC 9001" in drafts

    def test_detect_mixed_mentions(self):
        """Test detecting both draft and RFC mentions."""
        detector = DraftDetector()

        text = "See draft-ietf-quic-transport-34 and RFC 9000."
        drafts = detector.detect(text)

        assert len(drafts) == 2
        assert "draft-ietf-quic-transport-34" in drafts
        assert "RFC 9000" in drafts

    def test_no_mentions(self):
        """Test text with no mentions."""
        detector = DraftDetector()

        text = "This is just regular text with no draft or RFC mentions."
        drafts = detector.detect(text)

        assert len(drafts) == 0

    def test_empty_text(self):
        """Test with empty text."""
        detector = DraftDetector()

        drafts = detector.detect("")
        assert len(drafts) == 0

        drafts = detector.detect(None)
        assert len(drafts) == 0

    def test_duplicate_mentions(self):
        """Test that duplicate mentions are deduplicated."""
        detector = DraftDetector()

        text = "RFC 9000 is important. I repeat, RFC 9000 is important."
        drafts = detector.detect(text)

        assert len(drafts) == 1
        assert "RFC 9000" in drafts

    def test_case_insensitive(self):
        """Test case-insensitive detection."""
        detector = DraftDetector()

        text = "See rfc9000 and RFC9001"
        drafts = detector.detect(text)

        # Both should be normalized to "RFC XXXX" format
        assert len(drafts) == 2
        assert "RFC 9000" in drafts
        assert "RFC 9001" in drafts

    def test_custom_pattern(self):
        """Test with custom regex pattern."""
        # Custom pattern that only matches RFC
        detector = DraftDetector(pattern=r"RFC\s*\d+")

        text = "See draft-ietf-quic-transport-34 and RFC 9000"
        drafts = detector.detect(text)

        # Should only detect RFC with this pattern
        assert len(drafts) == 1
        assert "RFC 9000" in drafts
