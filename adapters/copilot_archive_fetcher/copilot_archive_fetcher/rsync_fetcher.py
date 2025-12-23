# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Rsync archive fetcher implementation."""

import logging
import os
import subprocess

from .base import ArchiveFetcher
from .models import SourceConfig

logger = logging.getLogger(__name__)


class RsyncFetcher(ArchiveFetcher):
    """Fetcher for rsync sources."""

    def __init__(self, source: SourceConfig):
        """Initialize rsync fetcher.

        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> tuple[bool, list | None, str | None]:
        """Fetch archives via rsync.

        Args:
            output_dir: Directory to store the fetched archives

        Returns:
            Tuple of (success, list_of_file_paths, error_message)
        """
        try:
            # Create output directory for this source
            source_dir = os.path.join(output_dir, self.source.name)
            os.makedirs(source_dir, exist_ok=True)

            # Build rsync command
            # Format: rsync://host/path or host::module/path
            rsync_url = self.source.url
            if not rsync_url.endswith("/"):
                rsync_url += "/"

            command = [
                "rsync",
                "-avz",
                "--delete",
                rsync_url,
                source_dir + "/",
            ]

            logger.info(f"Executing rsync: {' '.join(command)}")

            # Execute rsync
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode != 0:
                error_msg = f"rsync failed with code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                return False, None, error_msg

            logger.info(f"rsync completed successfully for source {self.source.name}")

            # Collect all files in the source directory
            file_paths = []
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_paths.append(file_path)

            logger.info(f"Found {len(file_paths)} files in {source_dir}")
            return True, file_paths, None

        except subprocess.TimeoutExpired as e:
            error_msg = f"rsync operation timed out: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"rsync fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
