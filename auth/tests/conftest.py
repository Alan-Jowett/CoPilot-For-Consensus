# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration for auth service tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all auth tests."""
    os.environ["SERVICE_VERSION"] = "0.1.0"

    # Set discriminant types for adapters (use noop/local for tests)
    os.environ["METRICS_TYPE"] = "noop"
    os.environ["DOCUMENT_STORE_TYPE"] = "mongodb"
    os.environ["SECRET_PROVIDER_TYPE"] = "local"
    os.environ["OIDC_PROVIDERS_TYPE"] = "multi"

    yield

    # Clean up environment variables
    os.environ.pop("SERVICE_VERSION", None)
    os.environ.pop("METRICS_TYPE", None)
    os.environ.pop("DOCUMENT_STORE_TYPE", None)
    os.environ.pop("SECRET_PROVIDER_TYPE", None)
    os.environ.pop("OIDC_PROVIDERS_TYPE", None)
