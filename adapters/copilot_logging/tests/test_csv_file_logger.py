# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for CSV file logger."""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from copilot_logging.csv_file_logger import CSVFileLogger


def test_csv_logger_creates_file(tmp_path: Path) -> None:
    """Test that CSV logger creates log file with headers."""
    logger = CSVFileLogger(
        log_path=str(tmp_path),
        component="test-service",
        replica_id="replica-1",
    )

    # Write a log entry
    logger.info("Test message", request_id="req-123", custom_field="value")

    # Check file exists
    log_files = list(tmp_path.glob("*.csv"))
    assert len(log_files) == 1

    # Read and verify content
    with open(log_files[0], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["level"] == "INFO"
    assert row["component"] == "test-service"
    assert row["replica_id"] == "replica-1"
    assert row["request_id"] == "req-123"
    assert row["message"] == "Test message"

    # Verify custom field is in json_extras
    extras = json.loads(row["json_extras"])
    assert extras["custom_field"] == "value"


def test_csv_logger_multiple_levels(tmp_path: Path) -> None:
    """Test logging at different levels."""
    logger = CSVFileLogger(log_path=str(tmp_path), component="test")

    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.debug("Debug message")
    logger.exception("Exception message")

    # Read all entries
    log_file = list(tmp_path.glob("*.csv"))[0]
    with open(log_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 5
    assert rows[0]["level"] == "INFO"
    assert rows[1]["level"] == "WARNING"
    assert rows[2]["level"] == "ERROR"
    assert rows[3]["level"] == "DEBUG"
    assert rows[4]["level"] == "EXCEPTION"


def test_csv_logger_daily_rotation(tmp_path: Path) -> None:
    """Test that log file name includes date."""
    logger = CSVFileLogger(
        log_path=str(tmp_path),
        component="test-service",
        replica_id="replica-1",
    )

    logger.info("Test message")

    # Check filename pattern
    log_files = list(tmp_path.glob("test-service_replica-1_*.csv"))
    assert len(log_files) == 1

    filename = log_files[0].name
    # Should match pattern: test-service_replica-1_YYYY-MM-DD.csv
    assert filename.startswith("test-service_replica-1_")
    assert filename.endswith(".csv")
    assert len(filename.split("_")) == 4  # service, replica, date, extension


def test_csv_logger_uses_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that logger respects environment variables."""
    monkeypatch.setenv("APP_LOG_PATH", str(tmp_path))
    monkeypatch.setenv("HOSTNAME", "test-host")

    logger = CSVFileLogger(component="service")
    logger.info("Test message")

    # Check file created in correct location
    assert len(list(tmp_path.glob("*.csv"))) == 1

    # Check replica_id comes from HOSTNAME
    log_file = list(tmp_path.glob("*.csv"))[0]
    with open(log_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
    assert row["replica_id"] == "test-host"
