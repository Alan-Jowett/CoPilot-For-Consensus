#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Test script to verify port exposure changes in docker-compose.yml

This script validates:
1. Public services expose ports on 0.0.0.0 (accessible from any interface)
2. Localhost services expose ports on 127.0.0.1 (accessible only from host)
3. Internal services have no port mappings (not accessible from host)
"""

import subprocess
import sys

import yaml


def load_compose_config():
    """Load and parse docker-compose.yml"""
    try:
        result = subprocess.run(["docker", "compose", "config"], capture_output=True, text=True, check=True)
        return yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to load docker-compose.yml: {e.stderr}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"✗ Failed to parse docker-compose config: {e}")
        sys.exit(1)


def check_port_binding(service_name, ports, expected_binding):
    """
    Check if service ports match expected binding

    Args:
        service_name: Name of the service
        ports: Port configuration from docker-compose
        expected_binding: Expected binding ('public', 'localhost', or 'none')

    Returns:
        tuple: (passed, message)
    """
    if expected_binding == "none":
        if ports is None or len(ports) == 0:
            return (True, f"✓ {service_name}: No port mappings (internal-only)")
        else:
            return (False, f"✗ {service_name}: Expected no ports, but found {ports}")

    if ports is None or len(ports) == 0:
        return (False, f"✗ {service_name}: Expected ports but none found")

    all_correct = True
    messages = []

    for port_spec in ports:
        # Parse port specification
        # Format can be "8080:8080", "127.0.0.1:8080:8080", or object with 'published' and 'target'
        if isinstance(port_spec, dict):
            published = str(port_spec.get("published", ""))
            target = str(port_spec.get("target", ""))
            port_spec.get("mode", "ingress")
            host_ip = port_spec.get("host_ip", "")
        else:
            parts = str(port_spec).split(":")
            if len(parts) == 3:
                host_ip, published, target = parts
            elif len(parts) == 2:
                host_ip = ""
                published, target = parts
            else:
                messages.append(f"  ⚠ {service_name}: Invalid port format: {port_spec}")
                all_correct = False
                continue

        # Check binding
        if expected_binding == "public":
            if host_ip and host_ip != "0.0.0.0":
                messages.append(
                    f"  ✗ {service_name}: Port {published} should be public (0.0.0.0 or empty), but bound to {host_ip}"
                )
                all_correct = False
            else:
                messages.append(f"  ✓ {service_name}: Port {published} correctly public")
        elif expected_binding == "localhost":
            if host_ip != "127.0.0.1":
                messages.append(
                    f"  ✗ {service_name}: Port {published} should be localhost-only (127.0.0.1), but bound to '{host_ip}'"
                )
                all_correct = False
            else:
                messages.append(f"  ✓ {service_name}: Port {published} correctly bound to localhost")

    if all_correct:
        return (True, f"✓ {service_name}: All ports correctly configured\n" + "\n".join(messages))
    else:
        return (False, f"✗ {service_name}: Port binding errors\n" + "\n".join(messages))


def main():
    """Main test function"""
    print("Testing Docker Compose port exposure configuration...\n")

    config = load_compose_config()
    services = config.get("services", {})

    # Define expected port bindings for each service
    expectations = {
        # Public services (accessible from any interface)
        "grafana": "public",
        "reporting": "public",
        # Localhost-only services (accessible only from host)
        "documentdb": "localhost",
        "messagebus": "localhost",
        "vectorstore": "localhost",
        "ollama": "localhost",
        "monitoring": "localhost",
        "loki": "localhost",
        "ingestion": "localhost",
        "ui": "localhost",
        # Internal-only services (no port mappings)
        "pushgateway": "none",
        "mongodb-exporter": "none",
        "mongo-doc-count-exporter": "none",
        "document-processing-exporter": "none",
        "qdrant-exporter": "none",
        "cadvisor": "none",
        # Processing services (no port mappings)
        "parsing": "none",
        "chunking": "none",
        "embedding": "none",
        "orchestrator": "none",
        "summarization": "none",
    }

    passed = 0
    failed = 0

    for service_name, expected_binding in expectations.items():
        if service_name not in services:
            print(f"⚠ {service_name}: Service not found in docker-compose.yml")
            continue

        service_config = services[service_name]
        ports = service_config.get("ports", None)

        success, message = check_port_binding(service_name, ports, expected_binding)
        print(message)

        if success:
            passed += 1
        else:
            failed += 1
        print()

    # Summary
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\n✗ Some port binding tests failed")
        sys.exit(1)
    else:
        print("\n✓ All port binding tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
