# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""CSV file logger for writing structured logs to Azure Files."""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .logger import Logger


class CSVFileLogger(Logger):
    """Logger that writes structured logs to CSV files.

    This logger is designed for use with Azure Files storage where each
    container replica writes to its own CSV file. Logs are appended in
    CSV format with a fixed schema and an extras column for additional fields.

    The CSV format is optimized for:
    - Easy parsing with standard tools (Excel, pandas, qsv, etc.)
    - Low storage overhead compared to JSON
    - Schema evolution via the json_extras column
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        component: str = "unknown",
        replica_id: Optional[str] = None,
    ):
        """Initialize CSV file logger.

        Args:
            log_path: Base directory for log files (default: /mnt/logs)
            component: Component/service name for log attribution
            replica_id: Replica identifier (default: hostname or 'default')
        """
        self.log_path = Path(log_path or os.getenv("APP_LOG_PATH", "/mnt/logs"))
        self.component = component
        self.replica_id = replica_id or os.getenv("HOSTNAME", "default")

        # Create log directory if it doesn't exist
        self.log_path.mkdir(parents=True, exist_ok=True)

        # CSV schema: fixed columns + json_extras for extensibility
        self.fieldnames = [
            "ts",
            "level",
            "component",
            "replica_id",
            "request_id",
            "message",
            "json_extras",
        ]

        # Log file rotation: one file per day per replica
        self._current_log_file: Optional[Path] = None
        self._current_date: Optional[str] = None

    def _get_log_file_path(self) -> Path:
        """Get current log file path with daily rotation."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Rotate log file if date changed
        if self._current_date != today:
            self._current_date = today
            self._current_log_file = (
                self.log_path / f"{self.component}_{self.replica_id}_{today}.csv"
            )

            # Write CSV header if new file
            if not self._current_log_file.exists():
                with open(self._current_log_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                    writer.writeheader()

        return self._current_log_file  # type: ignore

    def _write_log(self, level: str, message: str, **kwargs: Any) -> None:
        """Write a log entry to the CSV file.

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG, EXCEPTION)
            message: Log message
            **kwargs: Additional structured data
        """
        # Extract known fields
        request_id = kwargs.pop("request_id", "")
        ts = datetime.utcnow().isoformat() + "Z"

        # Put remaining fields in json_extras
        json_extras = json.dumps(kwargs, ensure_ascii=False) if kwargs else ""

        # Prepare row
        row = {
            "ts": ts,
            "level": level,
            "component": self.component,
            "replica_id": self.replica_id,
            "request_id": request_id,
            "message": message,
            "json_extras": json_extras,
        }

        # Append to log file
        log_file = self._get_log_file_path()
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(row)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info-level message."""
        self._write_log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning-level message."""
        self._write_log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message."""
        self._write_log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message."""
        self._write_log("DEBUG", message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an exception-level message."""
        self._write_log("EXCEPTION", message, **kwargs)
