# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base fetcher class and utilities."""

import hashlib
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ArchiveFetcher(ABC):
    """Abstract base class for archive fetchers."""

    @abstractmethod
    def fetch(self, output_dir: str) -> tuple[bool, list[str] | None, str | None]:
        """Fetch archive from source.

        Args:
            output_dir: Directory to store the fetched archive

        Returns:
            Tuple of (success: bool, list_of_file_paths: Optional[list[str]], error_message: Optional[str])
        """
        pass


def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate hash of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hash value in hexadecimal

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the algorithm is not supported
    """
    try:
        hash_obj = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from e

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()
