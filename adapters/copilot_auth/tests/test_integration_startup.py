#!/usr/bin/env python
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration test to simulate JWKS fetch during service startup.

This test simulates the scenario where a service starts up and attempts
to fetch JWKS from the auth service before it's fully ready.
"""

import http.server
import multiprocessing
import socketserver
import time

from copilot_auth.middleware import JWTMiddleware
from fastapi import FastAPI


def make_delayed_jwks_handler(start_time, ready_after_seconds=3):
    """Create an HTTP handler that delays responses to simulate auth service startup.

    The returned handler class captures start_time and ready_after_seconds so
    that each mock auth server instance can have its own independent timing
    configuration, avoiding shared mutable class state across tests.

    Args:
        start_time: The time when the server started
        ready_after_seconds: Seconds before the server becomes ready (default: 3)

    Returns:
        Handler class configured with the specified timing
    """

    class DelayedJWKSHandler(http.server.SimpleHTTPRequestHandler):
        """HTTP handler that delays responses to simulate auth service startup."""

        def do_GET(self):
            """Handle GET requests with delayed response for /keys endpoint."""
            if self.path == "/keys":
                elapsed = time.time() - start_time
                if elapsed < ready_after_seconds:
                    # Not ready yet - return 503
                    self.send_response(503)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Service starting up"}')
                    return

                # Ready - return JWKS
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                jwks = b'{"keys": [{"kty": "RSA", "kid": "test-key", "use": "sig"}]}'
                self.wfile.write(jwks)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            """Suppress logging output."""
            pass

    return DelayedJWKSHandler


def run_mock_auth_server(port, ready_event, actual_port_queue):
    """Run a mock auth server that delays JWKS responses.

    Args:
        port: Port to bind to (use 0 for dynamic port assignment)
        ready_event: Event to signal when server is ready
        actual_port_queue: Queue to communicate the actual port used
    """
    handler_cls = make_delayed_jwks_handler(start_time=time.time(), ready_after_seconds=3)
    with socketserver.TCPServer(("", port), handler_cls) as httpd:
        actual_port = httpd.server_address[1]
        actual_port_queue.put(actual_port)
        print(f"Mock auth server running on port {actual_port}")
        ready_event.set()
        # Run for 20 seconds
        for _ in range(20):
            httpd.handle_request()


def test_jwks_fetch_during_startup():
    """Test that middleware successfully fetches JWKS even when auth service is delayed."""
    ready_event = multiprocessing.Event()
    actual_port_queue = multiprocessing.Queue()

    # Start mock auth server in background with dynamic port (0 = OS assigns available port)
    server_process = multiprocessing.Process(target=run_mock_auth_server, args=(0, ready_event, actual_port_queue))
    server_process.start()

    try:
        # Wait for server to start and get the actual port
        ready_event.wait(timeout=5)
        port = actual_port_queue.get(timeout=5)
        time.sleep(0.1)

        # Create FastAPI app with JWT middleware
        # This simulates service startup
        print("Creating service with JWT middleware...")
        start_time = time.time()

        app = FastAPI()
        middleware = JWTMiddleware(
            app=app.router,
            auth_service_url=f"http://localhost:{port}",
            audience="test-service",
            jwks_fetch_retries=5,
            jwks_fetch_retry_delay=0.5,
            defer_jwks_fetch=False,  # Use synchronous for this test to verify retries work
        )

        elapsed = time.time() - start_time
        print(f"Middleware initialized in {elapsed:.2f} seconds")

        # Verify JWKS was fetched successfully
        assert middleware.jwks is not None, "JWKS should not be None"
        assert "keys" in middleware.jwks, "JWKS should have 'keys' field"
        assert len(middleware.jwks["keys"]) > 0, "JWKS should have at least one key"

        print("✓ JWKS fetch succeeded after retry")
        print(f"✓ JWKS contains {len(middleware.jwks['keys'])} key(s)")

    finally:
        server_process.terminate()
        server_process.join(timeout=2)
        if server_process.is_alive():
            server_process.kill()


if __name__ == "__main__":
    print("=" * 60)
    print("Integration Test: JWKS Fetch During Service Startup")
    print("=" * 60)
    print()
    print("This test simulates a service starting up while the auth")
    print("service is still initializing. The middleware should retry")
    print("until the auth service is ready.")
    print()

    test_jwks_fetch_during_startup()

    print()
    print("=" * 60)
    print("✓ Integration test passed!")
    print("=" * 60)
