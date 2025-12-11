# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures for parsing service tests."""

import os
import sys
import tempfile
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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
