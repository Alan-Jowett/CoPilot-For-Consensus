# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT middleware deferred JWKS fetch logic."""

import time
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
                "alg": "RS256",
            }
        ]
    }


def test_deferred_jwks_fetch_non_blocking_init(mock_jwks):
    """Test that deferred JWKS fetch doesn't block middleware initialization."""
    app = FastAPI()

    # Simulate slow JWKS endpoint
    with patch("copilot_auth.middleware.httpx.get") as mock_get:

        def slow_response(*args, **kwargs):
            time.sleep(2)  # Simulate 2 second delay
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()
            return mock_response

        mock_get.side_effect = slow_response

        # Measure initialization time
        start_time = time.time()
        middleware = JWTMiddleware(
            app=app.router,
            auth_service_url="http://auth:8090",
            audience="test-service",
            defer_jwks_fetch=True,  # Enable deferred fetch
            jwks_fetch_retries=1,
        )
        init_time = time.time() - start_time

        # Init should complete quickly (< 0.5s) even though JWKS fetch takes 2s
        assert init_time < 0.5, f"Init took {init_time:.2f}s, expected < 0.5s"

        # JWKS should be None initially
        assert middleware.jwks is None

        # Wait for background thread to complete
        if middleware._jwks_background_thread:
            middleware._jwks_background_thread.join(timeout=3.0)

        # JWKS should be loaded after background thread completes
        assert middleware.jwks == mock_jwks


def test_deferred_jwks_fetch_emergency_on_demand(mock_jwks):
    """Test that emergency on-demand fetch works when request arrives before background completes."""
    app = FastAPI()

    @app.get("/protected")
    def protected_endpoint():
        return {"message": "success"}

    # Mock slow background fetch and fast emergency fetch
    fetch_count = {"count": 0}

    def mock_get_side_effect(*args, **kwargs):
        fetch_count["count"] += 1
        if fetch_count["count"] == 1:
            # First call (background): slow
            time.sleep(5)  # Will timeout during emergency fetch
            raise httpx.TimeoutException("Background fetch timeout")
        else:
            # Second call (emergency): fast
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()
            return mock_response

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_get.side_effect = mock_get_side_effect

        middleware = JWTMiddleware(
            app=app.router,
            auth_service_url="http://auth:8090",
            audience="test-service",
            defer_jwks_fetch=True,
            jwks_fetch_retries=1,
        )

        # JWKS should be None initially (background fetch still running)
        assert middleware.jwks is None

        # Try to validate a token - this should trigger emergency fetch
        token_header = {"kid": "test-key-id", "alg": "RS256"}

        # Wait a moment for background thread to start
        time.sleep(0.1)

        # Call _get_public_key which should trigger emergency fetch
        with patch("copilot_auth.middleware.jwt.get_unverified_header", return_value=token_header):
            public_key = middleware._get_public_key(token_header)

        # JWKS should be loaded via emergency fetch
        assert middleware.jwks is not None
        # Verify public key was retrieved
        assert public_key is not None
        # At least 2 fetch attempts should have been made (background + emergency)
        assert fetch_count["count"] >= 2


def test_synchronous_jwks_fetch_backward_compatible(mock_jwks):
    """Test that synchronous JWKS fetch still works when defer_jwks_fetch=False."""
    app = FastAPI()

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Create middleware with synchronous fetch
        middleware = JWTMiddleware(
            app=app.router,
            auth_service_url="http://auth:8090",
            audience="test-service",
            defer_jwks_fetch=False,  # Disable deferred fetch
            jwks_fetch_retries=3,
        )

        # JWKS should be loaded immediately during init
        assert middleware.jwks == mock_jwks
        assert mock_get.call_count == 1

        # Background thread should not be started
        assert middleware._jwks_background_thread is None


def test_thread_safe_jwks_cache_updates(mock_jwks):
    """Test that JWKS cache updates are thread-safe."""
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
            defer_jwks_fetch=True,
            jwks_cache_ttl=1,  # 1 second TTL for testing
        )

        # Wait for initial background fetch
        if middleware._jwks_background_thread:
            middleware._jwks_background_thread.join(timeout=2.0)

        # Force multiple concurrent refreshes
        import threading

        def force_refresh():
            middleware._fetch_jwks(force=True)

        threads = [threading.Thread(target=force_refresh) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # JWKS should still be valid
        assert middleware.jwks == mock_jwks


def test_deferred_fetch_with_retry_on_failure(mock_jwks):
    """Test that deferred fetch retries on connection failures."""
    app = FastAPI()

    attempt_count = {"count": 0}

    def mock_get_side_effect(*args, **kwargs):
        attempt_count["count"] += 1
        if attempt_count["count"] < 3:
            # First 2 attempts fail
            raise httpx.ConnectError("Connection failed")
        else:
            # Third attempt succeeds
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = MagicMock()
            return mock_response

    with patch("copilot_auth.middleware.httpx.get") as mock_get:
        mock_get.side_effect = mock_get_side_effect

        with patch("copilot_auth.middleware.time.sleep"):  # Speed up test
            middleware = JWTMiddleware(
                app=app.router,
                auth_service_url="http://auth:8090",
                audience="test-service",
                defer_jwks_fetch=True,
                jwks_fetch_retries=5,
                jwks_fetch_retry_delay=0.1,
            )

            # Wait for background thread to complete
            if middleware._jwks_background_thread:
                middleware._jwks_background_thread.join(timeout=2.0)

        # JWKS should be loaded after retries
        assert middleware.jwks == mock_jwks
        assert attempt_count["count"] == 3
