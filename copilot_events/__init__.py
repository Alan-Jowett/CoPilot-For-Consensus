# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Events SDK.

A shared library for event publishing across microservices in the
Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .publisher import EventPublisher, create_publisher
from .rabbitmq import RabbitMQPublisher
from .noop import NoopPublisher
from .models import ArchiveIngestedEvent, ArchiveIngestionFailedEvent

__all__ = [
    "EventPublisher",
    "create_publisher",
    "RabbitMQPublisher",
    "NoopPublisher",
    "ArchiveIngestedEvent",
    "ArchiveIngestionFailedEvent",
]
