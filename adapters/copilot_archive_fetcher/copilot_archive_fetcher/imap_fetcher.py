# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""IMAP archive fetcher implementation."""

import logging
import os
import mailbox as mbox_module
from typing import Optional, Tuple

from .base import ArchiveFetcher
from .models import SourceConfig

logger = logging.getLogger(__name__)


class IMAPFetcher(ArchiveFetcher):
    """Fetcher for IMAP sources."""

    def __init__(self, source: SourceConfig):
        """Initialize IMAP fetcher.
        
        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> Tuple[bool, Optional[list], Optional[str]]:
        """Fetch emails via IMAP.
        
        Args:
            output_dir: Directory to store the fetched mbox file
            
        Returns:
            Tuple of (success, list_of_file_paths, error_message)
        """
        try:
            import imapclient

            os.makedirs(output_dir, exist_ok=True)

            host = self.source.url
            port = self.source.port or 993
            username = self.source.username
            password = self.source.password
            folder = self.source.folder or "INBOX"

            # Validate required credentials
            if not username or not password:
                error_msg = "IMAP credentials missing: 'username' and 'password' are required in the source configuration."
                logger.error(error_msg)
                return False, None, error_msg

            logger.info(f"Connecting to IMAP {host}:{port}")

            # Connect to IMAP server
            client = imapclient.IMAPClient(host, port=port, ssl=True)
            client.login(username, password)

            # Select folder
            client.select_folder(folder)

            # Get all message IDs
            msg_ids = client.search()
            logger.info(f"Found {len(msg_ids)} messages in {folder}")

            # Create mbox file
            filename = f"{self.source.name}_{folder.replace('/', '_')}.mbox"
            file_path = os.path.join(output_dir, filename)

            mbox = mbox_module.mbox(file_path)

            # Fetch all messages
            for msg_id in msg_ids:
                try:
                    msg_data = client.fetch([msg_id], ["RFC822"])
                    if msg_id in msg_data:
                        msg_bytes = msg_data[msg_id][b"RFC822"]
                        mbox.add(msg_bytes)
                except Exception as e:
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")

            mbox.close()
            client.logout()

            logger.info(f"Saved {len(msg_ids)} messages to {file_path}")
            return True, [file_path], None

        except ImportError as e:
            error_msg = f"Required library not installed: {e}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"IMAP fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
