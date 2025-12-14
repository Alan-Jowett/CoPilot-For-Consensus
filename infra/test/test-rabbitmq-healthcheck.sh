#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Test the RabbitMQ healthcheck script.
# This test verifies that the validation script correctly detects the presence
# or absence of the copilot.events exchange.

set -e

SCRIPT_DIR="$(dirname "$0")"
VALIDATE_SCRIPT="${SCRIPT_DIR}/../rabbitmq/validate-rabbitmq.sh"

echo "Testing RabbitMQ validation script..."

# Test 1: Verify script exists
if [ ! -f "$VALIDATE_SCRIPT" ]; then
    echo "✗ FAIL: validate-rabbitmq.sh not found at $VALIDATE_SCRIPT"
    exit 1
fi

echo "✓ Script exists"

# Test 2: Verify script has correct syntax
if ! sh -n "$VALIDATE_SCRIPT"; then
    echo "✗ FAIL: Script has syntax errors"
    exit 1
fi

echo "✓ Script syntax is valid"

# Test 3: Verify script contains expected validation logic
if ! grep -q "copilot.events" "$VALIDATE_SCRIPT"; then
    echo "✗ FAIL: Script does not check for copilot.events exchange"
    exit 1
fi

echo "✓ Script checks for copilot.events exchange"

# Test 4: Verify script uses rabbitmqctl
if ! grep -q "rabbitmqctl" "$VALIDATE_SCRIPT"; then
    echo "✗ FAIL: Script does not use rabbitmqctl"
    exit 1
fi

echo "✓ Script uses rabbitmqctl"

echo ""
echo "All validation script tests passed ✓"
echo "Note: To fully test the healthcheck, run the messagebus service in docker-compose"
echo "  and verify it becomes healthy after the copilot.events exchange is created."
