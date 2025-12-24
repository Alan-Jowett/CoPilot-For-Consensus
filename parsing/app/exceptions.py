# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Exceptions for parsing service operations."""


class ParsingError(Exception):
    """Base exception for parsing service errors."""
    pass


class MessageParsingError(ParsingError):
    """Raised when parsing an individual message fails."""

    def __init__(self, message: str, message_index: int = None):
        """Initialize MessageParsingError with context.

        Args:
            message: Error message
            message_index: Index of the message that failed to parse (optional)
        """
        super().__init__(message)
        self.message_index = message_index


class MboxFileError(ParsingError):
    """Raised when opening or reading an mbox file fails."""

    def __init__(self, message: str, file_path: str = None):
        """Initialize MboxFileError with context.

        Args:
            message: Error message
            file_path: Path to the mbox file that failed (optional)
        """
        super().__init__(message)
        self.file_path = file_path


class RequiredFieldMissingError(ParsingError):
    """Raised when a required field is missing from a message."""

    def __init__(self, field_name: str, message_id: str = None):
        """Initialize RequiredFieldMissingError.

        Args:
            field_name: Name of the missing required field
            message_id: Message ID where field is missing (optional)
        """
        message = f"Required field '{field_name}' is missing"
        if message_id:
            message += f" (message_id: {message_id})"
        super().__init__(message)
        self.field_name = field_name
        self.message_id = message_id
