# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import hashlib
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import SourceConfig

logger = logging.getLogger(__name__)


class ArchiveFetcher(ABC):
    """Abstract base class for archive fetchers."""

    @abstractmethod
    def fetch(self, output_dir: str) -> Tuple[bool, Optional[list], Optional[str]]:
        """Fetch archive from source.
        
        Args:
            output_dir: Directory to store the fetched archive
            
        Returns:
            Tuple of (success: bool, list_of_file_paths: Optional[list], error_message: Optional[str])
        """
        pass


class RsyncFetcher(ArchiveFetcher):
    """Fetcher for rsync sources."""

    def __init__(self, source: SourceConfig):
        """Initialize rsync fetcher.
        
        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> Tuple[bool, Optional[list], Optional[str]]:
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

        except subprocess.TimeoutExpired:
            error_msg = "rsync operation timed out"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"rsync fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg


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

        except ImportError:
            error_msg = "requests library not installed"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"HTTP fetch failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg


class LocalFetcher(ArchiveFetcher):
    """Fetcher for local filesystem sources."""

    def __init__(self, source: SourceConfig):
        """Initialize local fetcher.
        
        Args:
            source: Source configuration
        """
        self.source = source

    def fetch(self, output_dir: str) -> Tuple[bool, Optional[list], Optional[str]]:
        """Copy archive from local filesystem.
        
        Args:
            output_dir: Directory to store the copied archive
            
        Returns:
            Tuple of (success, list_of_file_paths, error_message)
        """
        try:
            import shutil

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
            import mailbox as mbox_module

            os.makedirs(output_dir, exist_ok=True)

            host = self.source.url
            port = self.source.port or 993
            username = self.source.username
            password = self.source.password
            folder = self.source.folder or "INBOX"

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


def create_fetcher(source: SourceConfig) -> ArchiveFetcher:
    """Factory function to create an archive fetcher.
    
    Args:
        source: Source configuration
        
    Returns:
        ArchiveFetcher instance
        
    Raises:
        ValueError: If source type is not supported
    """
    source_type = source.source_type.lower()

    if source_type == "rsync":
        return RsyncFetcher(source)
    elif source_type == "http":
        return HTTPFetcher(source)
    elif source_type == "local":
        return LocalFetcher(source)
    elif source_type == "imap":
        return IMAPFetcher(source)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")


def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hash value in hexadecimal
    """
    hash_obj = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()
