#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Validate that the copilot.events exchange exists in RabbitMQ.
# Exits non-zero if the exchange is not found.

set -e

# Wait for RabbitMQ to be ready
rabbitmqctl wait --timeout 60 /var/lib/rabbitmq/mnesia/rabbitmq.pid 2>/dev/null || true

# List exchanges and check for copilot.events
if rabbitmqctl list_exchanges name --formatter json | grep -q '"copilot.events"'; then
    echo "✓ RabbitMQ validation succeeded: copilot.events exchange exists"
    exit 0
else
    echo "✗ RabbitMQ validation failed: copilot.events exchange not found"
    exit 1
fi
