# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Thread data model for representing discussion threads."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """Represents a single message in a thread.

    Attributes:
        message_id: Unique identifier for the message
        author: Email address or name of the message author
        subject: Subject line of the message
        content: Body content of the message
        timestamp: When the message was sent
        in_reply_to: ID of the message this is replying to (if any)
        metadata: Additional metadata about the message
    """
    message_id: str
    author: str
    subject: str
    content: str
    timestamp: datetime
    in_reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Thread:
    """Represents a discussion thread.

    A thread consists of a root message and all its replies.

    Attributes:
        thread_id: Unique identifier for the thread (typically root message ID)
        subject: Thread subject line
        messages: List of messages in the thread
        started_at: Timestamp of the first message
        last_activity_at: Timestamp of the most recent message
        metadata: Additional metadata about the thread
    """
    thread_id: str
    subject: str
    messages: list[Message] = field(default_factory=list)
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Update timestamps from messages if not provided."""
        if self.messages:
            if self.started_at is None:
                self.started_at = min(msg.timestamp for msg in self.messages)
            if self.last_activity_at is None:
                self.last_activity_at = max(msg.timestamp for msg in self.messages)

    @property
    def message_count(self) -> int:
        """Return the number of messages in the thread."""
        return len(self.messages)

    @property
    def reply_count(self) -> int:
        """Return the number of replies (excluding root message)."""
        return max(0, len(self.messages) - 1)

    @property
    def participant_count(self) -> int:
        """Return the number of unique participants."""
        return len(set(msg.author for msg in self.messages))
