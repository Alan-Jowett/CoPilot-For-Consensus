# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the parsing service API."""

from unittest.mock import Mock

import pytest
from app.service import ParsingService
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def mock_document_store():
    """Create a mock document store."""
    store = Mock()
    store.insert_document = Mock(return_value="message_123")
    store.query_documents = Mock(return_value=[])
    return store


@pytest.fixture
def mock_publisher():
    """Create a mock event publisher."""
    publisher = Mock()
    publisher.publish = Mock()
    return publisher


@pytest.fixture
def mock_subscriber():
    """Create a mock event subscriber."""
    subscriber = Mock()
    subscriber.subscribe = Mock()
    return subscriber


@pytest.fixture
def mock_archive_store():
    """Create a mock archive store."""
    store = Mock()
    return store


@pytest.fixture
def test_service(mock_document_store, mock_publisher, mock_subscriber, mock_archive_store):
    """Create a test parsing service instance."""
    return ParsingService(
        document_store=mock_document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        archive_store=mock_archive_store,
    )


@pytest.fixture
def client(test_service, monkeypatch):
    """Create a test client with mocked service."""
    # Monkey patch the global service
    import main

    monkeypatch.setattr(main, "parsing_service", test_service)

    return TestClient(app)


@pytest.mark.integration
def test_readyz_endpoint_service_ready(client, test_service, monkeypatch):
    """Test /readyz endpoint when service is ready."""
    import main
    import threading

    # Mock subscriber thread as alive
    mock_thread = Mock(spec=threading.Thread)
    mock_thread.is_alive.return_value = True
    monkeypatch.setattr(main, "subscriber_thread", mock_thread)

    response = client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "parsing"


@pytest.mark.integration
def test_readyz_endpoint_service_not_initialized(client, monkeypatch):
    """Test /readyz endpoint when service is not initialized."""
    import main

    # Set service to None
    monkeypatch.setattr(main, "parsing_service", None)

    response = client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Service not initialized"


@pytest.mark.integration
def test_readyz_endpoint_subscriber_thread_not_running(client, test_service, monkeypatch):
    """Test /readyz endpoint when subscriber thread is not running."""
    import main

    # Set subscriber_thread to None
    monkeypatch.setattr(main, "subscriber_thread", None)

    response = client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Subscriber thread not running"


@pytest.mark.integration
def test_readyz_endpoint_subscriber_thread_dead(client, test_service, monkeypatch):
    """Test /readyz endpoint when subscriber thread is dead."""
    import main
    import threading

    # Mock subscriber thread as dead
    mock_thread = Mock(spec=threading.Thread)
    mock_thread.is_alive.return_value = False
    monkeypatch.setattr(main, "subscriber_thread", mock_thread)

    response = client.get("/readyz")

    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Subscriber thread not running"
