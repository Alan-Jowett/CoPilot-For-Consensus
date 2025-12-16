#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Quick validation script to verify port exposure changes don't break service communication.

This script tests:
1. Public services are accessible from host
2. Localhost services are accessible from host
3. Internal services can be reached by other containers (via Docker network)

NOTE: This is a basic smoke test. Some internal service endpoints may require
authentication or may vary by version. Test failures don't necessarily indicate
problems with port exposure - verify manually if needed.

Usage:
    python tests/validate_port_changes.py

Requirements:
    - Docker Compose stack must be running
    - requests library (pip install requests)
"""

import sys
import subprocess
import requests
import time


def check_service_accessible(url, service_name, timeout=5):
    """Check if a service is accessible via HTTP"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code < 500:  # Accept any non-500 status
            print(f"✓ {service_name} accessible at {url}")
            return True
        else:
            print(f"✗ {service_name} returned {response.status_code} at {url}")
            return False
    except requests.RequestException as e:
        print(f"✗ {service_name} not accessible at {url}: {e}")
        return False


def check_internal_service_via_docker(service_name, internal_url, from_service="reporting"):
    """Check if an internal service is accessible from another container"""
    try:
        cmd = [
            "docker", "compose", "exec", "-T", from_service,
            "python", "-c",
            f"import urllib.request; urllib.request.urlopen('{internal_url}', timeout=5)"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ {service_name} accessible internally from {from_service} container")
            return True
        else:
            print(f"✗ {service_name} not accessible internally: {result.stderr.decode()}")
            return False
    except Exception as e:
        print(f"✗ Failed to check {service_name}: {e}")
        return False


def main():
    """Main validation function"""
    print("Validating Docker Compose port exposure changes...\n")
    print("NOTE: This test requires the Docker Compose stack to be running.\n")
    
    passed = 0
    failed = 0
    
    # Test public services (should be accessible from host on 0.0.0.0)
    print("=" * 60)
    print("Testing PUBLIC services (0.0.0.0)...")
    print("=" * 60)
    
    public_services = [
        ("http://localhost:3000/api/health", "Grafana"),
        ("http://localhost:8080/health", "Reporting API"),
    ]
    
    for url, name in public_services:
        if check_service_accessible(url, name):
            passed += 1
        else:
            failed += 1
    
    # Test localhost-only services (should be accessible from host on 127.0.0.1)
    print("\n" + "=" * 60)
    print("Testing LOCALHOST-ONLY services (127.0.0.1)...")
    print("=" * 60)
    
    localhost_services = [
        ("http://localhost:9090/-/healthy", "Prometheus"),
        ("http://localhost:3100/ready", "Loki"),
        ("http://localhost:8083/health", "Reporting UI"),
        # Note: Can't easily test TCP services like MongoDB, RabbitMQ, Qdrant, Ollama via HTTP
    ]
    
    for url, name in localhost_services:
        if check_service_accessible(url, name):
            passed += 1
        else:
            failed += 1
    
    # Test that internal services are accessible via Docker network
    print("\n" + "=" * 60)
    print("Testing INTERNAL service communication (Docker network)...")
    print("=" * 60)
    
    internal_services = [
        ("pushgateway:9091", "Pushgateway", "http://pushgateway:9091/-/ready"),
        ("messagebus:15672", "RabbitMQ Management", "http://messagebus:15672/api/health"),
        ("vectorstore:6333", "Qdrant", "http://vectorstore:6333/healthz"),
    ]
    
    for _, name, url in internal_services:
        if check_internal_service_via_docker(name, url):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Validation Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        print("\n✗ Some validation checks failed")
        print("This may indicate:")
        print("  - Services are not running (run 'docker compose up -d' first)")
        print("  - Port binding changes broke service communication")
        print("  - Network connectivity issues")
        return 1
    else:
        print("\n✓ All validation checks passed!")
        print("Port exposure changes are working correctly.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
