# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures for embedding service tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all embedding tests."""
    os.environ["SERVICE_VERSION"] = "0.1.0"

    # Set discriminant types for adapters (use noop/inmemory for tests)
    os.environ["DOCUMENT_STORE_TYPE"] = "inmemory"
    os.environ["EMBEDDING_BACKEND_TYPE"] = "mock"
    os.environ["ERROR_REPORTER_TYPE"] = "console"
    os.environ["MESSAGE_BUS_TYPE"] = "noop"
    os.environ["METRICS_TYPE"] = "noop"
    os.environ["SECRET_PROVIDER_TYPE"] = "local"
    os.environ["VECTOR_STORE_TYPE"] = "qdrant"

    yield

    # Clean up environment variables
    os.environ.pop("SERVICE_VERSION", None)
    os.environ.pop("DOCUMENT_STORE_TYPE", None)
    os.environ.pop("EMBEDDING_BACKEND_TYPE", None)
    os.environ.pop("ERROR_REPORTER_TYPE", None)
    os.environ.pop("MESSAGE_BUS_TYPE", None)
    os.environ.pop("METRICS_TYPE", None)
    os.environ.pop("SECRET_PROVIDER_TYPE", None)
    os.environ.pop("VECTOR_STORE_TYPE", None)
