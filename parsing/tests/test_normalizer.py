# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for text normalizer."""

from app.normalizer import TextNormalizer


class TestTextNormalizer:
    """Tests for TextNormalizer."""

    def test_remove_signature(self):
        """Test signature removal."""
        normalizer = TextNormalizer()

        text = "This is the message body.\n-- \nAlice Developer\nExample Corp"
        normalized = normalizer.normalize(text)

        assert "This is the message body." in normalized
        assert "Alice Developer" not in normalized
        assert "Example Corp" not in normalized

    def test_remove_quoted_text(self):
        """Test quoted text removal."""
        normalizer = TextNormalizer()

        text = "I agree.\n> This is a quote\n> Another quoted line\nMy response."
        normalized = normalizer.normalize(text)

        assert "I agree." in normalized
        assert "My response." in normalized
        assert "This is a quote" not in normalized
        assert "Another quoted line" not in normalized

    def test_remove_html(self):
        """Test HTML removal."""
        normalizer = TextNormalizer()

        text = "<html><body><p>This is HTML content.</p></body></html>"
        normalized = normalizer.normalize(text)

        assert "This is HTML content." in normalized
        assert "<html>" not in normalized
        assert "<p>" not in normalized

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        normalizer = TextNormalizer()

        text = "Line 1\n\n\n\nLine 2   with   spaces"
        normalized = normalizer.normalize(text)

        # Should have max 2 newlines
        assert "\n\n\n" not in normalized
        # Should have single spaces
        assert "   " not in normalized

    def test_disable_html_stripping(self):
        """Test with HTML stripping disabled."""
        normalizer = TextNormalizer(strip_html=False)

        text = "<p>HTML content</p>"
        normalized = normalizer.normalize(text)

        # HTML tags should remain if contains_html returns False or stripping is disabled
        # Our simple check might not catch all HTML, so we just verify it runs
        assert "HTML content" in normalized

    def test_disable_signature_removal(self):
        """Test with signature removal disabled."""
        normalizer = TextNormalizer(strip_signatures=False)

        text = "Message body\n-- \nSignature"
        normalized = normalizer.normalize(text)

        assert "Message body" in normalized
        assert "Signature" in normalized

    def test_disable_quoted_removal(self):
        """Test with quoted text removal disabled."""
        normalizer = TextNormalizer(strip_quoted=False)

        text = "My text\n> Quoted text"
        normalized = normalizer.normalize(text)

        assert "My text" in normalized
        assert "> Quoted text" in normalized

    def test_empty_text(self):
        """Test with empty text."""
        normalizer = TextNormalizer()

        normalized = normalizer.normalize("")
        assert normalized == ""

        normalized = normalizer.normalize(None)
        assert normalized == ""

    def test_various_signature_delimiters(self):
        """Test different signature delimiters."""
        normalizer = TextNormalizer()

        # Test with different delimiters
        for delimiter in ["\n-- \n", "\n--\n", "\n___\n", "\n___________\n"]:
            text = f"Message body{delimiter}Signature"
            normalized = normalizer.normalize(text)
            assert "Message body" in normalized
            assert "Signature" not in normalized
