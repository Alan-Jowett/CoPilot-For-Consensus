# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the /providers endpoint."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_auth_service_no_providers():
    """Create a mock auth service with no providers configured."""
    service = MagicMock()
    service.providers = {}  # No providers configured
    return service


@pytest.fixture
def mock_auth_service_github_only():
    """Create a mock auth service with only GitHub configured."""
    service = MagicMock()
    service.providers = {"github": MagicMock()}  # Only GitHub
    return service


@pytest.fixture
def mock_auth_service_all_providers():
    """Create a mock auth service with all providers configured."""
    service = MagicMock()
    service.providers = {
        "github": MagicMock(),
        "google": MagicMock(),
        "microsoft": MagicMock(),
    }
    return service


def create_client(service):
    """Create test client with specified mock auth service."""
    with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
        import main
        main.auth_service = service
        return TestClient(main.app)


class TestProvidersEndpoint:
    """Test GET /providers endpoint."""

    def test_providers_endpoint_no_providers(self, mock_auth_service_no_providers):
        """Test /providers endpoint when no providers are configured."""
        client = create_client(mock_auth_service_no_providers)
        response = client.get("/providers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "providers" in data
        assert "configured_count" in data
        assert "total_supported" in data
        
        # Check counts
        assert data["configured_count"] == 0
        assert data["total_supported"] == 3
        
        # Check all three providers are listed as not configured
        assert "github" in data["providers"]
        assert "google" in data["providers"]
        assert "microsoft" in data["providers"]
        
        assert data["providers"]["github"]["configured"] is False
        assert data["providers"]["google"]["configured"] is False
        assert data["providers"]["microsoft"]["configured"] is False

    def test_providers_endpoint_github_only(self, mock_auth_service_github_only):
        """Test /providers endpoint when only GitHub is configured."""
        client = create_client(mock_auth_service_github_only)
        response = client.get("/providers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check counts
        assert data["configured_count"] == 1
        assert data["total_supported"] == 3
        
        # Check GitHub is configured, others are not
        assert data["providers"]["github"]["configured"] is True
        assert data["providers"]["github"]["available"] is True
        
        assert data["providers"]["google"]["configured"] is False
        assert data["providers"]["google"]["available"] is False
        
        assert data["providers"]["microsoft"]["configured"] is False
        assert data["providers"]["microsoft"]["available"] is False

    def test_providers_endpoint_all_configured(self, mock_auth_service_all_providers):
        """Test /providers endpoint when all providers are configured."""
        client = create_client(mock_auth_service_all_providers)
        response = client.get("/providers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check counts
        assert data["configured_count"] == 3
        assert data["total_supported"] == 3
        
        # Check all providers are configured
        assert data["providers"]["github"]["configured"] is True
        assert data["providers"]["google"]["configured"] is True
        assert data["providers"]["microsoft"]["configured"] is True

    def test_providers_endpoint_without_auth_service(self):
        """Test /providers endpoint when auth service is not initialized."""
        with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
            import main
            main.auth_service = None
            client = TestClient(main.app)
            
            response = client.get("/providers")
            
            assert response.status_code == 503
            data = response.json()
            assert "not initialized" in data["detail"].lower()
