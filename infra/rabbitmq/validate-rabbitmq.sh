#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Validate that the copilot.events exchange exists in RabbitMQ.
# Exits non-zero if the exchange is not found.

set -e

# Wait for RabbitMQ to be ready
# Timeout set to 4s to fit within Docker healthcheck timeout of 5s
rabbitmqctl wait --timeout 4 /var/lib/rabbitmq/mnesia/rabbitmq.pid >/dev/null

# List exchanges and check for copilot.events
# Use -x flag to match exact line (exchange name only)
if rabbitmqctl list_exchanges name | grep -qx "copilot.events"; then
    echo "✓ RabbitMQ validation succeeded: copilot.events exchange exists"
    exit 0
else
    echo "✗ RabbitMQ validation failed: copilot.events exchange not found"
    exit 1
fi
