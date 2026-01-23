#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for validate_auth_service_health.py script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from validate_auth_service_health import AuthServiceValidator


class TestAuthServiceValidator:
    """Tests for AuthServiceValidator."""

    @pytest.fixture
    def mock_requests(self):
        """Mock requests library."""
        with patch("validate_auth_service_health.requests") as mock:
            yield mock

    def test_health_endpoint_success(self, mock_requests):
        """Test successful health endpoint check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "service": "auth",
            "version": "1.0.0"
        }
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_health_endpoint()

        assert result is True
        assert validator.checks_passed == 1
        assert validator.checks_failed == 0

    def test_health_endpoint_unhealthy(self, mock_requests):
        """Test health endpoint with unhealthy status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unhealthy"}
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_health_endpoint()

        assert result is False
        assert validator.checks_passed == 0
        assert validator.checks_failed == 1

    def test_readyz_endpoint_not_ready(self, mock_requests):
        """Test readiness endpoint when service not ready."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"detail": "Service not ready"}
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_readyz_endpoint()

        assert result is False
        assert validator.checks_passed == 0
        assert validator.checks_failed == 1

    def test_jwks_endpoint_success(self, mock_requests):
        """Test successful JWKS endpoint check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": "default",
                    "alg": "RS256",
                    "n": "test_modulus",
                    "e": "AQAB"
                }
            ]
        }
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_jwks_endpoint()

        assert result is True
        assert validator.checks_passed == 1
        assert validator.checks_failed == 0

    def test_jwks_endpoint_500_error(self, mock_requests):
        """Test JWKS endpoint with 500 error (Key Vault permission issue).
        
        This is the critical regression test for the issue where Key Vault
        permission errors cause JWKS endpoints to return 500.
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "detail": "Failed to retrieve public keys for token validation"
        }
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_jwks_endpoint()

        assert result is False
        assert validator.checks_passed == 0
        assert validator.checks_failed == 1

    def test_jwks_endpoint_empty_keys(self, mock_requests):
        """Test JWKS endpoint with empty keys array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"keys": []}
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_jwks_endpoint()

        assert result is False
        assert validator.checks_passed == 0
        assert validator.checks_failed == 1

    def test_jwks_endpoint_invalid_jwk_format(self, mock_requests):
        """Test JWKS endpoint with invalid JWK format (missing required fields)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "keys": [
                {
                    "kty": "RSA",
                    # Missing: use, kid, alg
                }
            ]
        }
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_jwks_endpoint()

        assert result is False
        assert validator.checks_passed == 0
        assert validator.checks_failed == 1

    def test_providers_endpoint_success(self, mock_requests):
        """Test successful providers endpoint check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "providers": {
                "github": {"configured": True},
                "google": {"configured": False},
                "microsoft": {"configured": False}
            },
            "configured_count": 1,
            "total_supported": 3
        }
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.check_providers_endpoint()

        assert result is True
        assert validator.checks_passed == 1
        assert validator.checks_failed == 0

    def test_run_all_checks_success(self, mock_requests):
        """Test running all checks successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"status": "healthy", "service": "auth", "version": "1.0.0"},
            {"status": "ready"},
            {"keys": [{"kty": "RSA", "use": "sig", "kid": "default", "alg": "RS256"}]},
            {"keys": [{"kty": "RSA", "use": "sig", "kid": "default", "alg": "RS256"}]},
            {"providers": {}, "configured_count": 0, "total_supported": 3},
        ]
        mock_requests.get.return_value = mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.run_all_checks()

        assert result is True
        assert validator.checks_passed == 5
        assert validator.checks_failed == 0

    def test_run_all_checks_with_jwks_failure(self, mock_requests):
        """Test running all checks with JWKS endpoint failure.
        
        This simulates the Key Vault permission error scenario where
        health and readiness pass but JWKS fails.
        """
        mock_response = MagicMock()
        responses = [
            (200, {"status": "healthy", "service": "auth", "version": "1.0.0"}),
            (200, {"status": "ready"}),
            (500, {"detail": "Failed to retrieve public keys"}),  # JWKS fails
            (500, {"detail": "Failed to retrieve public keys"}),  # Well-known JWKS fails
            (200, {"providers": {}, "configured_count": 0, "total_supported": 3}),
        ]

        def get_mock_response(*args, **kwargs):
            status, data = responses.pop(0)
            resp = MagicMock()
            resp.status_code = status
            resp.json.return_value = data
            return resp

        mock_requests.get.side_effect = get_mock_response

        validator = AuthServiceValidator("http://localhost:8090")
        result = validator.run_all_checks()

        assert result is False
        assert validator.checks_passed == 3  # health, readiness, providers
        assert validator.checks_failed == 2  # both JWKS endpoints
