# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT middleware JWKS fetch retry logic."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from copilot_auth.middleware import JWTMiddleware
from fastapi import FastAPI


@pytest.fixture
def mock_jwks():
    """Mock JWKS response."""
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": "test-key-id",
                "n": "test-modulus",
                "e": "AQAB",
            }
        ]
    }


def test_jwks_fetch_retry_success_on_first_attempt(mock_jwks):
    """Test JWKS fetch succeeds on first attempt."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        middleware = JWTMiddleware(
            app=app.router,
            auth_service_url="http://auth:8090",
            audience="test-service",
            jwks_fetch_retries=3,
            jwks_fetch_retry_delay=0.1,
            defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
        )

        # Verify JWKS was fetched successfully
        assert middleware.jwks == mock_jwks
        assert mock_get.call_count == 1


def test_jwks_fetch_retry_success_on_second_attempt(mock_jwks):
    """Test JWKS fetch succeeds after one retry."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        # First call raises TimeoutException, second succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status = MagicMock()

        mock_get.side_effect = [
            httpx.TimeoutException("Connection timeout"),
            mock_response,
        ]

        with patch("copilot_auth.middleware.time.sleep"):  # Speed up test by mocking sleep
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify JWKS was fetched successfully on second attempt
        assert middleware.jwks == mock_jwks
        assert mock_get.call_count == 2


def test_jwks_fetch_retry_failure_after_max_attempts():
    """Test JWKS fetch fails after max retry attempts."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        # All calls raise TimeoutException
        mock_get.side_effect = httpx.TimeoutException("Connection timeout")

        with patch("copilot_auth.middleware.time.sleep"):  # Speed up test by mocking sleep
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify JWKS is empty after all retries failed
        assert middleware.jwks == {"keys": []}
        assert mock_get.call_count == 3


@pytest.mark.parametrize(
    "status_code,error_message",
    [
        (500, "Internal server error"),
        (502, "Bad gateway"),
        (503, "Service unavailable"),
        (504, "Gateway timeout"),
    ],
)
def test_jwks_fetch_retry_with_5xx_errors(mock_jwks, status_code, error_message):
    """Test JWKS fetch retries on 5xx server errors."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        # First call raises HTTPStatusError with 5xx status, second succeeds
        mock_error_response = MagicMock()
        mock_error_response.status_code = status_code

        mock_success_response = MagicMock()
        mock_success_response.json.return_value = mock_jwks
        mock_success_response.raise_for_status = MagicMock()

        mock_get.side_effect = [
            httpx.HTTPStatusError(error_message, request=MagicMock(), response=mock_error_response),
            mock_success_response,
        ]

        with patch("copilot_auth.middleware.time.sleep"):  # Speed up test by mocking sleep
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify JWKS was fetched successfully after 5xx retry
        assert middleware.jwks == mock_jwks
        assert mock_get.call_count == 2


def test_jwks_fetch_no_retry_on_404_error():
    """Test JWKS fetch does not retry on 404 Not Found."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        # Call raises HTTPStatusError with 404
        mock_404_response = MagicMock()
        mock_404_response.status_code = 404

        mock_get.side_effect = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_404_response)

        with patch("copilot_auth.middleware.time.sleep"):  # Speed up test by mocking sleep
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify JWKS is empty and only 1 attempt was made (no retries for 404)
        assert middleware.jwks == {"keys": []}
        assert mock_get.call_count == 1


def test_jwks_fetch_exponential_backoff():
    """Test JWKS fetch uses exponential backoff between retries."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Connection timeout")

        with patch("copilot_auth.middleware.time.sleep") as mock_sleep:
            JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=4,
                jwks_fetch_retry_delay=1.0,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

            # Verify exponential backoff: 1s, 2s, 4s (3 sleeps for 4 attempts)
            assert mock_sleep.call_count == 3
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls == [1.0, 2.0, 4.0]


def test_jwks_fetch_connect_error_retry():
    """Test JWKS fetch retries on connection errors."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with patch("copilot_auth.middleware.time.sleep"):
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify retries were attempted
        assert middleware.jwks == {"keys": []}
        assert mock_get.call_count == 3


def test_jwks_fetch_no_retry_on_unexpected_exception():
    """Test JWKS fetch does not retry on unexpected exceptions."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_get.side_effect = ValueError("Unexpected error")

        with patch("copilot_auth.middleware.time.sleep"):
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                jwks_fetch_retries=3,
                jwks_fetch_retry_delay=0.1,
                defer_jwks_fetch=False,  # Use synchronous fetch for deterministic testing
            )

        # Verify only 1 attempt was made (no retries for unexpected errors)
        assert middleware.jwks == {"keys": []}
        assert mock_get.call_count == 1
