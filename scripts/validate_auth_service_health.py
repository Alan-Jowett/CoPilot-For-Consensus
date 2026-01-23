#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Post-deploy validation script for auth service health.

This script validates that the auth service is properly deployed and functioning,
with a specific focus on Key Vault integration and JWKS endpoint health to prevent
regressions of Key Vault permission errors.

Usage:
    # For local docker-compose deployment
    python3 scripts/validate_auth_service_health.py --url http://localhost:8090

    # For Azure deployment
    python3 scripts/validate_auth_service_health.py --url https://copilot-auth-dev.azurecontainerapps.io

Exit codes:
    0: All checks passed
    1: One or more checks failed
    2: Script error (invalid arguments, etc.)
"""

import argparse
import json
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests library not found. Install with: pip install requests")
    sys.exit(2)


class AuthServiceValidator:
    """Validator for auth service health and JWKS endpoints."""

    # Required JWK fields for validation (per RFC 7517)
    REQUIRED_JWK_FIELDS = ["kty", "use", "kid", "alg"]

    def __init__(self, base_url: str, timeout: int = 10):
        """Initialize validator.

        Args:
            base_url: Base URL of auth service (e.g., http://localhost:8090)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.checks_passed = 0
        self.checks_failed = 0

    def check_health_endpoint(self) -> bool:
        """Check /health endpoint.

        Returns:
            True if health check passed
        """
        url = f"{self.base_url}/health"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    print(f"✓ Health endpoint: {url} - OK")
                    print(f"  Service: {data.get('service')}, Version: {data.get('version')}")
                    self.checks_passed += 1
                    return True
                else:
                    print(f"✗ Health endpoint: {url} - Status is not 'healthy': {data.get('status')}")
                    self.checks_failed += 1
                    return False
            else:
                print(f"✗ Health endpoint: {url} - HTTP {response.status_code}")
                self.checks_failed += 1
                return False
        except requests.RequestException as e:
            print(f"✗ Health endpoint: {url} - Request failed: {e}")
            self.checks_failed += 1
            return False

    def check_readyz_endpoint(self) -> bool:
        """Check /readyz endpoint.

        Returns:
            True if readiness check passed
        """
        url = f"{self.base_url}/readyz"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ready":
                    print(f"✓ Readiness endpoint: {url} - OK")
                    self.checks_passed += 1
                    return True
                else:
                    print(f"✗ Readiness endpoint: {url} - Status is not 'ready': {data.get('status')}")
                    self.checks_failed += 1
                    return False
            else:
                print(f"✗ Readiness endpoint: {url} - HTTP {response.status_code}")
                if response.status_code == 503:
                    try:
                        detail = response.json().get("detail", "Unknown")
                        print(f"  Detail: {detail}")
                    except Exception:
                        pass
                self.checks_failed += 1
                return False
        except requests.RequestException as e:
            print(f"✗ Readiness endpoint: {url} - Request failed: {e}")
            self.checks_failed += 1
            return False

    def check_jwks_endpoint(self) -> bool:
        """Check /keys (JWKS) endpoint.

        This is critical for Key Vault integration - validates that JWKS
        endpoint returns valid public keys without 500 errors.

        Returns:
            True if JWKS check passed
        """
        url = f"{self.base_url}/keys"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if "keys" in data:
                    keys = data["keys"]
                    if isinstance(keys, list) and len(keys) > 0:
                        # Validate first key has required JWK fields
                        key = keys[0]
                        missing_fields = [f for f in self.REQUIRED_JWK_FIELDS if f not in key]
                        if not missing_fields:
                            print(f"✓ JWKS endpoint: {url} - OK")
                            print(f"  Keys: {len(keys)}, Algorithm: {key.get('alg')}, Key ID: {key.get('kid')}")
                            self.checks_passed += 1
                            return True
                        else:
                            print(f"✗ JWKS endpoint: {url} - Invalid JWK format, missing: {missing_fields}")
                            self.checks_failed += 1
                            return False
                    else:
                        print(f"✗ JWKS endpoint: {url} - No keys in JWKS response")
                        self.checks_failed += 1
                        return False
                else:
                    print(f"✗ JWKS endpoint: {url} - Missing 'keys' field in response")
                    self.checks_failed += 1
                    return False
            elif response.status_code == 500:
                print(f"✗ JWKS endpoint: {url} - HTTP 500 (CRITICAL: Key Vault permission error?)")
                try:
                    detail = response.json().get("detail", "Unknown")
                    print(f"  Detail: {detail}")
                except Exception:
                    pass
                self.checks_failed += 1
                return False
            elif response.status_code == 503:
                print(f"✗ JWKS endpoint: {url} - HTTP 503 (Service not ready)")
                self.checks_failed += 1
                return False
            else:
                print(f"✗ JWKS endpoint: {url} - HTTP {response.status_code}")
                self.checks_failed += 1
                return False
        except requests.RequestException as e:
            print(f"✗ JWKS endpoint: {url} - Request failed: {e}")
            self.checks_failed += 1
            return False

    def check_wellknown_jwks_endpoint(self) -> bool:
        """Check /.well-known/jwks.json endpoint.

        Returns:
            True if well-known JWKS check passed
        """
        url = f"{self.base_url}/.well-known/jwks.json"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if "keys" in data and isinstance(data["keys"], list):
                    print(f"✓ Well-known JWKS endpoint: {url} - OK")
                    self.checks_passed += 1
                    return True
                else:
                    print(f"✗ Well-known JWKS endpoint: {url} - Invalid format")
                    self.checks_failed += 1
                    return False
            else:
                print(f"✗ Well-known JWKS endpoint: {url} - HTTP {response.status_code}")
                self.checks_failed += 1
                return False
        except requests.RequestException as e:
            print(f"✗ Well-known JWKS endpoint: {url} - Request failed: {e}")
            self.checks_failed += 1
            return False

    def check_providers_endpoint(self) -> bool:
        """Check /providers endpoint.

        Returns:
            True if providers check passed
        """
        url = f"{self.base_url}/providers"
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if "providers" in data:
                    configured_count = data.get("configured_count", 0)
                    total_supported = data.get("total_supported", 0)
                    print(f"✓ Providers endpoint: {url} - OK")
                    print(f"  Configured: {configured_count}/{total_supported}")
                    self.checks_passed += 1
                    return True
                else:
                    print(f"✗ Providers endpoint: {url} - Invalid format")
                    self.checks_failed += 1
                    return False
            else:
                print(f"✗ Providers endpoint: {url} - HTTP {response.status_code}")
                self.checks_failed += 1
                return False
        except requests.RequestException as e:
            print(f"✗ Providers endpoint: {url} - Request failed: {e}")
            self.checks_failed += 1
            return False

    def run_all_checks(self) -> bool:
        """Run all validation checks.

        Returns:
            True if all checks passed
        """
        print(f"\n=== Auth Service Validation ===")
        print(f"Target: {self.base_url}\n")

        # Run checks in order of importance
        checks = [
            ("Health", self.check_health_endpoint),
            ("Readiness", self.check_readyz_endpoint),
            ("JWKS (/keys)", self.check_jwks_endpoint),
            ("Well-known JWKS", self.check_wellknown_jwks_endpoint),
            ("Providers", self.check_providers_endpoint),
        ]

        for name, check_fn in checks:
            try:
                check_fn()
            except Exception as e:
                print(f"✗ {name} check - Unexpected error: {e}")
                self.checks_failed += 1

        # Print summary
        print(f"\n=== Summary ===")
        print(f"Checks passed: {self.checks_passed}")
        print(f"Checks failed: {self.checks_failed}")

        return self.checks_failed == 0


def wait_for_service(base_url: str, max_wait_seconds: int = 60, check_interval: int = 5) -> bool:
    """Wait for service to become available.

    Args:
        base_url: Base URL of auth service
        max_wait_seconds: Maximum time to wait
        check_interval: Seconds between checks

    Returns:
        True if service became available
    """
    print(f"Waiting for service at {base_url} (max {max_wait_seconds}s)...")
    url = f"{base_url.rstrip('/')}/health"
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✓ Service is available")
                return True
        except requests.RequestException:
            pass

        remaining = max(0, max_wait_seconds - (time.time() - start_time))
        print(f"  Waiting... ({remaining:.0f}s remaining)")
        time.sleep(check_interval)

    print(f"✗ Service did not become available within {max_wait_seconds}s")
    return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate auth service health and JWKS endpoints"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Base URL of auth service (e.g., http://localhost:8090)",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="Wait for service to become available (seconds, default: 0 = no wait)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )

    args = parser.parse_args()

    # Wait for service if requested
    if args.wait > 0:
        if not wait_for_service(args.url, max_wait_seconds=args.wait):
            sys.exit(1)

    # Run validation
    validator = AuthServiceValidator(args.url, timeout=args.timeout)
    success = validator.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
