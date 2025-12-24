# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Text normalization for email messages."""

import re

# Try to import BeautifulSoup, but provide fallback
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False


class TextNormalizer:
    """Normalizes email message bodies."""

    # Common email signature delimiters
    SIGNATURE_DELIMITERS = [
        "\n-- \n",
        "\n--\n",
        "\n___\n",
        "\n___________\n",
        "\n________________________________________\n",
    ]

    def __init__(
        self,
        strip_html: bool = True,
        strip_signatures: bool = True,
        strip_quoted: bool = True,
    ):
        """Initialize text normalizer.

        Args:
            strip_html: Whether to remove HTML tags
            strip_signatures: Whether to remove email signatures
            strip_quoted: Whether to remove quoted reply text
        """
        self.strip_html = strip_html
        self.strip_signatures = strip_signatures
        self.strip_quoted = strip_quoted

    def normalize(self, text: str) -> str:
        """Normalize email body text.

        Args:
            text: Raw email body text

        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""

        # Strip HTML tags if present
        if self.strip_html and self._contains_html(text):
            text = self._remove_html(text)

        # Remove email signatures
        if self.strip_signatures:
            text = self._remove_signature(text)

        # Remove quoted replies
        if self.strip_quoted:
            text = self._remove_quoted_text(text)

        # Normalize whitespace
        text = self._normalize_whitespace(text)

        return text.strip()

    def _contains_html(self, text: str) -> bool:
        """Check if text contains HTML tags.

        Args:
            text: Text to check

        Returns:
            True if HTML tags are detected
        """
        # Simple check for common HTML tags
        html_patterns = [
            r'<html',
            r'<body',
            r'<div',
            r'<p>',
            r'<br>',
            r'<span',
            r'<table',
        ]

        text_lower = text.lower()
        return any(pattern in text_lower for pattern in html_patterns)

    def _remove_html(self, text: str) -> str:
        """Remove HTML tags and convert to plain text.

        Args:
            text: HTML text

        Returns:
            Plain text with HTML tags removed
        """
        if BEAUTIFULSOUP_AVAILABLE:
            soup = BeautifulSoup(text, "html.parser")
            return soup.get_text()
        else:
            # Simple fallback: remove HTML tags with regex
            # WARNING: This is not secure for untrusted input and should only be used
            # as a last resort when BeautifulSoup is not available.
            # For production use, ensure beautifulsoup4 is installed.
            # The regex patterns here are intentionally simple and may not catch all edge cases.
            text = re.sub(r'<style(?:\s[^>]*)?>.*?</style(?:\s[^>]*)?>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<script(?:\s[^>]*)?>.*?</script(?:\s[^>]*)?>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            # Decode common HTML entities
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&amp;', '&')
            text = text.replace('&quot;', '"')
            text = text.replace('&#39;', "'")
            return text

    def _remove_signature(self, text: str) -> str:
        """Remove email signature after common delimiters.

        Args:
            text: Email body text

        Returns:
            Text with signature removed
        """
        for delimiter in self.SIGNATURE_DELIMITERS:
            if delimiter in text:
                text = text.split(delimiter)[0]
                break

        return text

    def _remove_quoted_text(self, text: str) -> str:
        """Remove quoted reply lines (starting with > or >>).

        Args:
            text: Email body text

        Returns:
            Text with quoted lines removed
        """
        lines = text.split('\n')
        filtered_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip lines that start with quote markers
            if stripped and not stripped.startswith(('>', '|', '>>')):
                filtered_lines.append(line)
            elif not stripped:
                # Keep blank lines
                filtered_lines.append(line)

        return '\n'.join(filtered_lines)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Text to normalize

        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r'[ \t]+', ' ', text)

        # Replace more than 2 consecutive newlines with 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text
