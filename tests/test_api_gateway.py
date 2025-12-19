# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Integration test for API Gateway routing.

This test validates that the NGINX API Gateway correctly routes requests
to the appropriate backend services.

Usage:
    pytest tests/test_api_gateway.py -v

Requirements:
    - Docker Compose stack must be running
    - All services must be healthy (gateway, reporting, ui, grafana)
"""

import subprocess
import time

import pytest
import requests


@pytest.fixture(scope="module")
def gateway_url():
    """Base URL for the API Gateway."""
    return "http://localhost:8080"


@pytest.fixture(scope="module")
def wait_for_services():
    """Wait for services to be healthy before running tests."""
    # Wait up to 30 seconds for gateway to be healthy
    for _ in range(30):
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "gateway", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                check=True
            )
            if "(healthy)" in result.stdout:
                time.sleep(2)  # Extra buffer for stability
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(1)
    
    pytest.fail("Gateway service did not become healthy within timeout")


class TestAPIGatewayRouting:
    """Test cases for API Gateway routing functionality."""
    
    def test_gateway_health_endpoint(self, gateway_url, wait_for_services):
        """Test that the gateway health check endpoint is accessible."""
        response = requests.get(f"{gateway_url}/health", timeout=5)
        assert response.status_code == 200
        assert response.text.strip() == "OK"
    
    def test_root_redirects_to_ui(self, gateway_url, wait_for_services):
        """Test that root path redirects to /ui/."""
        response = requests.get(gateway_url, allow_redirects=False, timeout=5)
        assert response.status_code == 302
        assert response.headers.get("Location") == "/ui/"
    
    def test_api_endpoint_routing(self, gateway_url, wait_for_services):
        """Test that /api/ routes to reporting service."""
        # Try accessing the reporting API via gateway
        try:
            response = requests.get(f"{gateway_url}/api/reports", timeout=5)
            # Should get 200 (with data) or 404 (no reports yet) - both indicate routing works
            assert response.status_code in [200, 404], \
                f"Expected 200 or 404, got {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.fail("Failed to connect to reporting API via gateway")
    
    def test_ui_endpoint_routing(self, gateway_url, wait_for_services):
        """Test that /ui/ routes to web UI service."""
        response = requests.get(f"{gateway_url}/ui/", timeout=5)
        assert response.status_code == 200
        # UI should return HTML
        assert "html" in response.headers.get("Content-Type", "").lower()
    
    def test_grafana_endpoint_routing(self, gateway_url, wait_for_services):
        """Test that /grafana/ routes to Grafana service."""
        response = requests.get(f"{gateway_url}/grafana/", timeout=5)
        # Grafana may redirect to login or return 200
        assert response.status_code in [200, 301, 302], \
            f"Expected 200, 301, or 302, got {response.status_code}"
    
    def test_cors_headers_on_api(self, gateway_url, wait_for_services):
        """Test that CORS headers are present on API endpoints."""
        headers = {"Origin": "http://example.com"}
        response = requests.get(f"{gateway_url}/api/", headers=headers, timeout=5)
        
        # Check for CORS headers
        assert "Access-Control-Allow-Origin" in response.headers, \
            "CORS headers missing from API response"
        assert response.headers["Access-Control-Allow-Origin"] == "*"
    
    def test_options_request_handling(self, gateway_url, wait_for_services):
        """Test that OPTIONS requests are handled correctly (CORS preflight)."""
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        }
        response = requests.options(f"{gateway_url}/api/", headers=headers, timeout=5)
        assert response.status_code == 204
        assert "Access-Control-Allow-Origin" in response.headers


class TestDirectServiceAccess:
    """Test that direct service access still works on localhost."""
    
    def test_reporting_direct_access(self):
        """Test direct access to reporting service on localhost:8090."""
        try:
            response = requests.get("http://localhost:8090/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("Reporting service not accessible on localhost:8090")
    
    def test_ui_direct_access(self):
        """Test direct access to UI service on localhost:8084."""
        try:
            response = requests.get("http://localhost:8084/", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("UI service not accessible on localhost:8084")
    
    def test_grafana_direct_access(self):
        """Test direct access to Grafana service on localhost:3000."""
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("Grafana service not accessible on localhost:3000")


if __name__ == "__main__":
    # Allow running as a standalone script for quick testing
    pytest.main([__file__, "-v"])
