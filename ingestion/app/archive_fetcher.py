# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import hashlib
import os
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any

from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector
from copilot_reporting import create_error_reporter, ErrorReporter

from .config import SourceConfig

logger = create_logger(name="ingestion.archive_fetcher")
metrics = create_metrics_collector()
error_reporter = create_error_reporter()


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

    def __init__(self, source: SourceConfig, metrics_collector: Optional[Any] = None, error_reporter_instance: Optional[ErrorReporter] = None):
        """Initialize rsync fetcher.
        
        Args:
            source: Source configuration
            metrics_collector: Metrics collector for observability (optional)
            error_reporter_instance: Error reporter for reporting errors (optional)
        """
        self.source = source
        self.metrics = metrics_collector or metrics
        self.error_reporter = error_reporter_instance or error_reporter

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

            # Execute rsync and track timing
            start_time = time.time()
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
            duration = time.time() - start_time

            if result.returncode != 0:
                error_msg = f"rsync failed with code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                self.metrics.increment("fetcher_rsync_failures_total", tags={
                    "source_name": self.source.name,
                })
                return False, None, error_msg

            logger.info(f"rsync completed successfully for source {self.source.name}")
            self.metrics.observe("fetcher_rsync_duration_seconds", duration, tags={
                "source_name": self.source.name,
            })

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
            self.metrics.increment("fetcher_rsync_timeouts_total", tags={
                "source_name": self.source.name,
            })
            self.error_reporter.capture_message(
                error_msg,
                level="error",
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "source_url": self.source.url,
                    "operation": "rsync_fetch",
                }
            )
            return False, None, error_msg
        except Exception as e:
            error_msg = f"rsync fetch failed: {str(e)}"
            logger.error(error_msg)
            self.metrics.increment("fetcher_rsync_errors_total", tags={
                "source_name": self.source.name,
                "error_type": type(e).__name__,
            })
            self.error_reporter.report(
                e,
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "source_url": self.source.url,
                    "operation": "rsync_fetch",
                }
            )
            return False, None, error_msg


class HTTPFetcher(ArchiveFetcher):
    """Fetcher for HTTP sources."""

    def __init__(self, source: SourceConfig, metrics_collector: Optional[Any] = None):
        """Initialize HTTP fetcher.
        
        Args:
            source: Source configuration
            metrics_collector: Metrics collector for observability (optional)
            error_reporter_instance: Error reporter for reporting errors (optional)
        """
        self.source = source
        self.metrics = metrics_collector or metrics
        self.error_reporter = error_reporter_instance or error_reporter

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

            # Track download timing
            start_time = time.time()
            response = requests.get(self.source.url, timeout=3600, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            duration = time.time() - start_time
            file_size = os.path.getsize(file_path)
            
            self.metrics.observe("fetcher_http_duration_seconds", duration, tags={
                "source_name": self.source.name,
            })
            self.metrics.observe("fetcher_downloaded_bytes", file_size, tags={
                "source_name": self.source.name,
            })

            logger.info(f"Downloaded {file_path}")
            return True, [file_path], None

        except ImportError:
            error_msg = "requests library not installed"
            logger.error(error_msg)
            self.metrics.increment("fetcher_http_import_errors_total", tags={
                "source_name": self.source.name,
            })
            self.error_reporter.capture_message(
                error_msg,
                level="error",
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "source_url": self.source.url,
                    "operation": "http_fetch",
                }
            )
            return False, None, error_msg
        except Exception as e:
            error_msg = f"HTTP fetch failed: {str(e)}"
            logger.error(error_msg)
            self.metrics.increment("fetcher_http_errors_total", tags={
                "source_name": self.source.name,
                "error_type": type(e).__name__,
            })
            self.error_reporter.report(
                e,
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "source_url": self.source.url,
                    "operation": "http_fetch",
                }
            )
            return False, None, error_msg


class LocalFetcher(ArchiveFetcher):
    """Fetcher for local filesystem sources."""

    def __init__(self, source: SourceConfig, metrics_collector: Optional[Any] = None, error_reporter_instance: Optional[ErrorReporter] = None):
        """Initialize local fetcher.
        
        Args:
            source: Source configuration
            metrics_collector: Metrics collector for observability (optional)
            error_reporter_instance: Error reporter for reporting errors (optional)
        """
        self.source = source
        self.metrics = metrics_collector or metrics
        self.error_reporter = error_reporter_instance or error_reporter

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
                self.metrics.increment("fetcher_local_errors_total", tags={
                    "source_name": self.source.name,
                    "error_type": "path_not_found",
                })
                self.error_reporter.capture_message(
                    error_msg,
                    level="warning",
                    context={
                        "source_name": self.source.name,
                        "source_type": self.source.source_type,
                        "source_path": source_path,
                        "operation": "local_fetch",
                    }
                )
                return False, None, error_msg

            os.makedirs(output_dir, exist_ok=True)

            start_time = time.time()
            
            if os.path.isfile(source_path):
                # Copy single file
                filename = os.path.basename(source_path)
                file_path = os.path.join(output_dir, filename)
                shutil.copy2(source_path, file_path)
                file_size = os.path.getsize(file_path)
                duration = time.time() - start_time
                
                self.metrics.observe("fetcher_local_duration_seconds", duration, tags={
                    "source_name": self.source.name,
                    "copy_type": "file",
                })
                self.metrics.observe("fetcher_copied_bytes", file_size, tags={
                    "source_name": self.source.name,
                })
                
                logger.info(f"Copied {source_path} to {file_path}")
                return True, [file_path], None
            elif os.path.isdir(source_path):
                # Copy directory and collect all files
                dest_path = os.path.join(output_dir, self.source.name)
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                
                # Collect all files in the copied directory
                file_paths = []
                total_size = 0
                for root, dirs, files in os.walk(dest_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_paths.append(file_path)
                        total_size += os.path.getsize(file_path)
                
                duration = time.time() - start_time
                
                self.metrics.observe("fetcher_local_duration_seconds", duration, tags={
                    "source_name": self.source.name,
                    "copy_type": "directory",
                })
                self.metrics.observe("fetcher_copied_bytes", total_size, tags={
                    "source_name": self.source.name,
                })
                
                logger.info(f"Copied directory {source_path} to {dest_path} ({len(file_paths)} files)")
                return True, file_paths, None
            else:
                error_msg = f"Source is neither file nor directory: {source_path}"
                logger.error(error_msg)
                self.metrics.increment("fetcher_local_errors_total", tags={
                    "source_name": self.source.name,
                    "error_type": "invalid_type",
                })
                self.error_reporter.capture_message(
                    error_msg,
                    level="warning",
                    context={
                        "source_name": self.source.name,
                        "source_type": self.source.source_type,
                        "source_path": source_path,
                        "operation": "local_fetch",
                    }
                )
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Local fetch failed: {str(e)}"
            logger.error(error_msg)
            self.metrics.increment("fetcher_local_errors_total", tags={
                "source_name": self.source.name,
                "error_type": type(e).__name__,
            })
            self.error_reporter.report(
                e,
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "source_path": self.source.url,
                    "operation": "local_fetch",
                }
            )
            return False, None, error_msg


class IMAPFetcher(ArchiveFetcher):
    """Fetcher for IMAP sources."""

    def __init__(self, source: SourceConfig, metrics_collector: Optional[Any] = None, error_reporter_instance: Optional[ErrorReporter] = None):
        """Initialize IMAP fetcher.
        
        Args:
            source: Source configuration
            metrics_collector: Metrics collector for observability (optional)
            error_reporter_instance: Error reporter for reporting errors (optional)
        """
        self.source = source
        self.metrics = metrics_collector or metrics
        self.error_reporter = error_reporter_instance or error_reporter

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

            # Validate required credentials
            if not username or not password:
                error_msg = "IMAP credentials missing: 'username' and 'password' are required in the source configuration."
                logger.error(error_msg)
                self.error_reporter.capture_message(
                    error_msg,
                    level="error",
                    context={
                        "source_name": self.source.name,
                        "source_type": self.source.source_type,
                        "host": host,
                        "operation": "imap_fetch",
                    }
                )
                return False, None, error_msg

            logger.info(f"Connecting to IMAP {host}:{port}")

            # Connect to IMAP server
            try:
                client = imapclient.IMAPClient(host, port=port, ssl=True)
                client.login(username, password)
            except Exception as e:
                error_msg = f"IMAP connection or login failed: {str(e)}"
                logger.error(error_msg)
                self.metrics.increment("fetcher_imap_auth_errors_total", tags={
                    "source_name": self.source.name,
                })
                self.error_reporter.report(
                    e,
                    context={
                        "source_name": self.source.name,
                        "source_type": self.source.source_type,
                        "host": host,
                        "operation": "imap_connect_login",
                    }
                )
                return False, None, error_msg

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
            failed_msg_count = 0
            for msg_id in msg_ids:
                try:
                    msg_data = client.fetch([msg_id], ["RFC822"])
                    if msg_id in msg_data:
                        msg_bytes = msg_data[msg_id][b"RFC822"]
                        mbox.add(msg_bytes)
                except Exception as e:
                    failed_msg_count += 1
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")

            mbox.close()
            client.logout()

            if failed_msg_count > 0:
                self.error_reporter.capture_message(
                    f"Failed to fetch {failed_msg_count} messages from IMAP",
                    level="warning",
                    context={
                        "source_name": self.source.name,
                        "source_type": self.source.source_type,
                        "host": host,
                        "folder": folder,
                        "failed_message_count": failed_msg_count,
                        "total_messages": len(msg_ids),
                    }
                )

            logger.info(f"Saved {len(msg_ids)} messages to {file_path}")
            return True, [file_path], None

        except ImportError as e:
            error_msg = f"Required library not installed: {e}"
            logger.error(error_msg)
            self.error_reporter.report(
                e,
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "operation": "imap_fetch",
                }
            )
            return False, None, error_msg
        except Exception as e:
            error_msg = f"IMAP fetch failed: {str(e)}"
            logger.error(error_msg)
            self.metrics.increment("fetcher_imap_errors_total", tags={
                "source_name": self.source.name,
                "error_type": type(e).__name__,
            })
            self.error_reporter.report(
                e,
                context={
                    "source_name": self.source.name,
                    "source_type": self.source.source_type,
                    "host": self.source.url,
                    "folder": self.source.folder or "INBOX",
                    "operation": "imap_fetch",
                }
            )
            return False, None, error_msg


def create_fetcher(source: SourceConfig, metrics_collector: Optional[Any] = None, error_reporter_instance: Optional[ErrorReporter] = None) -> ArchiveFetcher:
    """Factory function to create an archive fetcher.
    
    Args:
        source: Source configuration
        metrics_collector: Metrics collector for observability (optional)
        error_reporter_instance: Error reporter for reporting errors (optional)
        
    Returns:
        ArchiveFetcher instance
        
    Raises:
        ValueError: If source type is not supported
    """
    source_type = source.source_type.lower()

    if source_type == "rsync":
        return RsyncFetcher(source, metrics_collector, error_reporter_instance)
    elif source_type == "http":
        return HTTPFetcher(source, metrics_collector, error_reporter_instance)
    elif source_type == "local":
        return LocalFetcher(source, metrics_collector, error_reporter_instance)
    elif source_type == "imap":
        return IMAPFetcher(source, metrics_collector, error_reporter_instance)
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
