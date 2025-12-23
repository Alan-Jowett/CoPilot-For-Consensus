# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""HTTP archive fetcher implementation."""

import logging
import os
from typing import Optional, Tuple

from .base import ArchiveFetcher
from .models import SourceConfig

logger = logging.getLogger(__name__)


class HTTPFetcher(ArchiveFetcher):
    """Fetcher for HTTP sources."""

    def __init__(self, source: SourceConfig):
        """Initialize HTTP fetcher.

        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> Tuple[bool, Optional[list], Optional[str]]:
        """Fetch archive via HTTP.

        Args:
            output_dir: Directory to store the fetched archive

        Returns:
            Tuple of (success, list_of_file_paths, error_message)
        """
        try:
            import requests

            os.makedirs(output_dir, exist_ok=True)

            # Extract filename from URL
            filename = os.path.basename(self.source.url.rstrip("/"))
            if not filename:
                filename = f"{self.source.name}.mbox"

            file_path = os.path.join(output_dir, filename)

            logger.info(f"Downloading {self.source.url} to {file_path}")

            response = requests.get(self.source.url, timeout=3600, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded {file_path}")
            return True, [file_path], None

        except ImportError as e:
            error_msg = "requests library not installed"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"HTTP fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
