#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Test script to verify RabbitMQ per-queue metrics configuration.

This script validates:
1. messagebus service has PROMETHEUS_RETURN_PER_OBJECT_METRICS environment variable set
2. The rabbitmq_prometheus plugin is enabled in enabled_plugins
"""

import subprocess
import sys
import yaml


def load_compose_config():
    """Load and parse merged docker-compose configuration"""
    try:
        result = subprocess.run(
            ["docker", "compose", "config"],
            capture_output=True,
            text=True,
            check=True
        )
        return yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to load docker-compose configuration: {e.stderr}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"✗ Failed to parse docker-compose config: {e}")
        sys.exit(1)


def check_messagebus_env_var(config):
    """Check if messagebus service has PROMETHEUS_RETURN_PER_OBJECT_METRICS set"""
    services = config.get('services', {})
    messagebus = services.get('messagebus', {})
    
    # Check if the environment variable is set in the command
    # The command can be a string or a list, so normalize it to a string
    command = messagebus.get('command', '')
    if isinstance(command, list):
        command_str = ' '.join(str(c) for c in command)
    else:
        command_str = str(command)
    
    # Look for the environment variable export statement with word boundaries
    import re
    pattern = r'\bPROMETHEUS_RETURN_PER_OBJECT_METRICS\s*=\s*true\b'
    if re.search(pattern, command_str):
        return True, "PROMETHEUS_RETURN_PER_OBJECT_METRICS=true found in messagebus command"
    
    return False, "PROMETHEUS_RETURN_PER_OBJECT_METRICS not set to true in messagebus command"


def check_rabbitmq_plugin():
    """Check if rabbitmq_prometheus plugin is enabled"""
    try:
        with open('infra/rabbitmq/enabled_plugins', 'r') as f:
            content = f.read()
            if 'rabbitmq_prometheus' in content:
                return True, "rabbitmq_prometheus plugin is enabled"
            return False, "rabbitmq_prometheus plugin not found in enabled_plugins"
    except FileNotFoundError:
        return False, "infra/rabbitmq/enabled_plugins file not found"
    except Exception as e:
        return False, f"Error reading enabled_plugins: {e}"


def main():
    """Run all validation checks"""
    print("RabbitMQ Per-Queue Metrics Configuration Test")
    print("=" * 50)
    
    config = load_compose_config()
    
    all_passed = True
    
    # Check 1: PROMETHEUS_RETURN_PER_OBJECT_METRICS environment variable
    passed, message = check_messagebus_env_var(config)
    status = "✓" if passed else "✗"
    print(f"{status} {message}")
    all_passed = all_passed and passed
    
    # Check 2: rabbitmq_prometheus plugin enabled
    passed, message = check_rabbitmq_plugin()
    status = "✓" if passed else "✗"
    print(f"{status} {message}")
    all_passed = all_passed and passed
    
    print("=" * 50)
    if all_passed:
        print("✓ All checks passed")
        sys.exit(0)
    else:
        print("✗ Some checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
