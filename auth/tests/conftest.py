# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration for auth service tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all auth tests."""
    os.environ["SERVICE_VERSION"] = "0.1.0"

    yield

    os.environ.pop("SERVICE_VERSION", None)
