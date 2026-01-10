# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures for parsing service tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from copilot_message_bus import create_publisher, create_subscriber
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all tests."""
    # Service version for schema compatibility
    os.environ["SERVICE_VERSION"] = "0.1.0"
    
    # Required config fields for parsing service (fail-fast policy)
    os.environ["MESSAGE_BUS_TYPE"] = "noop"
    os.environ["DOCUMENT_STORE_TYPE"] = "in_memory"
    os.environ["ARCHIVE_STORE_TYPE"] = "local"
    os.environ["METRICS_BACKEND"] = "noop"
    os.environ["ERROR_REPORTER_TYPE"] = "noop"
    
    yield
    
    # Cleanup
    for key in ["SERVICE_VERSION", "MESSAGE_BUS_TYPE", "DOCUMENT_STORE_TYPE", 
                "ARCHIVE_STORE_TYPE", "METRICS_BACKEND", "ERROR_REPORTER_TYPE"]:
        os.environ.pop(key, None)


@pytest.fixture
def document_store():
    """Create in-memory document store with schema validation."""
    # Wrap with validation using document schemas
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
    schema_provider = create_schema_provider(schema_dir=schema_dir, schema_type="documents")

    store = create_document_store(
        driver_name="inmemory",
        driver_config={"schema_provider": schema_provider},
        enable_validation=True,
    )
    store.connect()
    return store


@pytest.fixture
def publisher():
    """Create a noop publisher for testing."""
    pub = create_publisher(driver_name="noop", driver_config={})
    pub.connect()
    return pub


@pytest.fixture
def subscriber():
    """Create a noop subscriber for testing."""
    sub = create_subscriber(driver_name="noop", driver_config={"queue_name": "json.parsed"})
    sub.connect()
    return sub


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_mbox_content():
    """Sample mbox content for testing."""
    return """From alice@example.com Mon Jan 01 00:00:00 2024
From: Alice Developer <alice@example.com>
To: quic@ietf.org
Subject: QUIC connection migration
Message-ID: <msg1@example.com>
Date: Mon, 01 Jan 2024 12:00:00 +0000

I think we should consider the approach outlined in draft-ietf-quic-transport-34.
This addresses the connection migration concerns.

--
Alice Developer
Example Corp

From bob@example.com Mon Jan 01 00:01:00 2024
From: Bob Engineer <bob@example.com>
To: quic@ietf.org
Subject: Re: QUIC connection migration
Message-ID: <msg2@example.com>
In-Reply-To: <msg1@example.com>
References: <msg1@example.com>
Date: Mon, 01 Jan 2024 12:30:00 +0000

> I think we should consider the approach outlined in draft-ietf-quic-transport-34.

I agree. Also see RFC 9000 for related context.

--
Bob Engineer

"""


@pytest.fixture
def sample_mbox_file(temp_dir, sample_mbox_content):
    """Create a sample mbox file for testing."""
    mbox_path = os.path.join(temp_dir, "test.mbox")
    with open(mbox_path, "w") as f:
        f.write(sample_mbox_content)
    return mbox_path


@pytest.fixture
def corrupted_mbox_file(temp_dir):
    """Create a corrupted mbox file for testing."""
    mbox_path = os.path.join(temp_dir, "corrupted.mbox")
    with open(mbox_path, "w") as f:
        f.write("This is not a valid mbox file\n")
    return mbox_path
