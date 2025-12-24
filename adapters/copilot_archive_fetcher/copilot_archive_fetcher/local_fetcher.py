# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local filesystem archive fetcher implementation."""

import logging
import os
import shutil

from .base import ArchiveFetcher
from .models import SourceConfig

logger = logging.getLogger(__name__)


class LocalFetcher(ArchiveFetcher):
    """Fetcher for local filesystem sources."""

    def __init__(self, source: SourceConfig):
        """Initialize local fetcher.

        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> tuple[bool, list[str] | None, str | None]:
        """Copy archive from local filesystem.

        Args:
            output_dir: Directory to store the copied archive

        Returns:
            Tuple of (success, list_of_file_paths, error_message)
        """
        try:
            source_path = self.source.url

            if not os.path.exists(source_path):
                error_msg = f"Source path does not exist: {source_path}"
                logger.error(error_msg)
                return False, None, error_msg

            os.makedirs(output_dir, exist_ok=True)

            if os.path.isfile(source_path):
                # Copy single file
                filename = os.path.basename(source_path)
                file_path = os.path.join(output_dir, filename)
                shutil.copy2(source_path, file_path)
                logger.info(f"Copied {source_path} to {file_path}")
                return True, [file_path], None
            elif os.path.isdir(source_path):
                # Copy directory and collect all files
                dest_path = os.path.join(output_dir, self.source.name)
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)

                # Collect all files in the copied directory
                file_paths = []
                for root, dirs, files in os.walk(dest_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_paths.append(file_path)

                logger.info(f"Copied directory {source_path} to {dest_path} ({len(file_paths)} files)")
                return True, file_paths, None
            else:
                error_msg = f"Source is neither file nor directory: {source_path}"
                logger.error(error_msg)
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Local fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
