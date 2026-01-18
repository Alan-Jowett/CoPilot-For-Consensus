# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Thread relationship building for email messages."""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ThreadBuilder:
    """Builds thread relationships from parsed messages."""

    def build_threads(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build thread documents from parsed messages.

        This method:
        1. Identifies root messages (messages with no in_reply_to)
        2. Groups messages by thread_id
        3. Aggregates thread metadata

        Args:
            messages: List of parsed message dictionaries

        Returns:
            List of thread dictionaries
        """
        if not messages:
            return []

        # First pass: build message lookup and identify roots
        message_map = {}
        roots = set()

        for message in messages:
            message_id = message["message_id"]
            message_map[message_id] = message

            # If no in_reply_to, this is a root message
            if not message.get("in_reply_to"):
                roots.add(message_id)

        # Second pass: assign thread_ids by tracing back to roots
        thread_assignments = {}

        for message in messages:
            message_id = message["message_id"]
            root = self._find_thread_root(message_id, message_map, roots)
            # If the root isn't present in the parsed set (e.g., missing parent), fall back to this message's _id
            if root not in message_map:
                logger.warning("Root message %s not found in parsed set; using current message's _id", root)
                if "_id" not in message:
                    raise KeyError("Message missing '_id' field; all messages must have an '_id' before threading.")
                root_doc_id = message["_id"]
            else:
                if "_id" not in message_map[root]:
                    raise KeyError(
                        "Root message missing '_id' field; all messages must have an '_id' before threading."
                    )
                root_doc_id = message_map[root]["_id"]
            thread_assignments[message_id] = root_doc_id
            # Update the message's thread_id to root message's canonical _id
            message["thread_id"] = root_doc_id

        # Third pass: aggregate threads
        threads = {}

        for message in messages:
            thread_doc_id = message["thread_id"]  # Now this is the root message's _id

            if thread_doc_id not in threads:
                # Initialize thread - use root message's _id as thread _id
                threads[thread_doc_id] = {
                    "_id": thread_doc_id,
                    "thread_id": thread_doc_id,
                    "archive_id": message["archive_id"],
                    "subject": self._clean_subject(message.get("subject", "")),
                    "participants": [],
                    "participant_emails": set(),  # For deduplication
                    "message_count": 0,
                    "first_message_date": message.get("date"),
                    "last_message_date": message.get("date"),
                    "draft_mentions": set(),
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }

            thread = threads[thread_doc_id]
            thread["message_count"] += 1

            # Update participants (deduplicate by email)
            from_addr = message.get("from")
            if from_addr and from_addr.get("email"):
                email = from_addr["email"]
                if email not in thread["participant_emails"]:
                    thread["participant_emails"].add(email)
                    thread["participants"].append(from_addr)

            # Update date range
            msg_date = message.get("date")
            if msg_date:
                if not thread["first_message_date"] or msg_date < thread["first_message_date"]:
                    thread["first_message_date"] = msg_date
                if not thread["last_message_date"] or msg_date > thread["last_message_date"]:
                    thread["last_message_date"] = msg_date

            # Aggregate draft mentions
            for draft in message.get("draft_mentions", []):
                thread["draft_mentions"].add(draft)

        # Clean up threads for storage
        for thread in threads.values():
            # Remove temporary participant_emails set
            del thread["participant_emails"]
            # Convert draft_mentions set to list
            thread["draft_mentions"] = list(thread["draft_mentions"])
            # Add default values for consensus fields
            thread["has_consensus"] = False
            thread["consensus_type"] = None
            thread["summary_id"] = None

        return list(threads.values())

    def _find_thread_root(
        self,
        message_id: str,
        message_map: dict[str, dict[str, Any]],
        known_roots: set[str],
        max_depth: int = 100,
    ) -> str:
        """Find the root message ID for a thread by following in_reply_to chain.

        Args:
            message_id: Message ID to find root for
            message_map: Map of message_id to message dict
            known_roots: Set of known root message IDs
            max_depth: Maximum depth to traverse (prevents infinite loops)

        Returns:
            Root message ID for the thread
        """
        # If this is a known root, return it
        if message_id in known_roots:
            return message_id

        visited = set()
        current_id = message_id
        depth = 0

        while depth < max_depth:
            # Check if we've seen this ID before (circular reference)
            if current_id in visited:
                logger.warning(f"Circular reference detected in thread starting at {message_id}")
                return message_id

            visited.add(current_id)

            # Get the message
            message = message_map.get(current_id)
            if not message:
                # Message not in our set, use current_id as root
                return current_id

            # Check if this is a root (no in_reply_to)
            in_reply_to = message.get("in_reply_to")
            if not in_reply_to:
                # This is a root
                known_roots.add(current_id)
                return current_id

            # Move up the chain
            current_id = in_reply_to
            depth += 1

        # Hit max depth, return the current position
        logger.warning(f"Max depth reached while finding root for {message_id}")
        return current_id

    def _clean_subject(self, subject: str) -> str:
        """Clean subject line by removing Re:, Fwd:, etc.

        Args:
            subject: Subject line

        Returns:
            Cleaned subject
        """
        if not subject:
            return ""

        # Remove common prefixes (case insensitive) in a loop
        import re

        # Keep removing prefixes until no more matches
        prev = None
        while prev != subject:
            prev = subject
            # Remove Re:, Fwd:, etc.
            subject = re.sub(r"^(Re:|RE:|Fwd:|FWD:|FW:)\s*", "", subject, flags=re.IGNORECASE)
            # Remove [list-name] prefixes
            subject = re.sub(r"^\[.*?\]\s*", "", subject)
            subject = subject.strip()

        return subject
