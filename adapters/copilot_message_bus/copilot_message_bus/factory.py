# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating message bus publishers and subscribers."""

import logging
from typing import Any

from copilot_config.models import DriverConfig

from .base import EventPublisher, EventSubscriber

logger = logging.getLogger(__name__)


def _get_schema_provider() -> Any:
    """Load a schema provider for validation.
    
    Returns:
        Schema provider instance.

    Raises:
        ImportError: If copilot_schema_validation is not installed.
    """
    try:
        from copilot_schema_validation import create_schema_provider  # type: ignore[import-not-found]
        return create_schema_provider()
    except ImportError as e:
        raise ImportError(
            "Schema validation requested but copilot_schema_validation is not installed. "
            "Install with: pip install copilot-message-bus[validation]"
        ) from e

def create_publisher(
    driver_name: str,
    driver_config: DriverConfig,
    enable_validation: bool = True,
    strict_validation: bool = True,
) -> EventPublisher:
    """Factory function to create an event publisher.

    By default, returns a validating publisher that enforces schema validation.
    This ensures all events are validated before being published.

    Usage:
        create_publisher(driver_name="rabbitmq", driver_config=driver_config)

    Args:
        driver_name: Type of message bus ("rabbitmq", "azureservicebus", or "noop")
        driver_config: DriverConfig instance with driver configuration.
        enable_validation: If True (default), wraps the publisher in ValidatingEventPublisher.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but publishing proceeds.

    Returns:
        EventPublisher instance (ValidatingEventPublisher by default)

    Raises:
        ValueError: If driver_name is not recognized
        ValueError: If required parameters are missing for the specified driver
    """
    driver_name_lower = driver_name.lower()

    # Create base publisher
    if driver_name_lower == "rabbitmq":
        from .rabbitmq_publisher import RabbitMQPublisher
        base_publisher = RabbitMQPublisher.from_config(driver_config)
    elif driver_name_lower in ("azureservicebus", "servicebus"):
        from .azureservicebuspublisher import AzureServiceBusPublisher
        base_publisher = AzureServiceBusPublisher.from_config(driver_config)
    elif driver_name_lower == "noop":
        from .noop_publisher import NoopPublisher
        base_publisher = NoopPublisher.from_config(driver_config)
    else:
        raise ValueError(
            f"Unknown driver_name: {driver_name}. "
            "Supported: 'rabbitmq', 'azureservicebus', 'noop'"
        )
    
    # Wrap in validating publisher if enabled
    if enable_validation:
        from .validating_publisher import ValidatingEventPublisher
        schema_provider = _get_schema_provider()
        return ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=strict_validation,
        )
    
    return base_publisher


def create_subscriber(
    driver_name: str,
    driver_config: DriverConfig,
    enable_validation: bool = True,
    strict_validation: bool = True,
) -> EventSubscriber:
    """Factory function to create an event subscriber.

    By default, returns a validating subscriber that enforces schema validation.
    This ensures all received events are validated before being passed to callbacks.

    Usage:
        create_subscriber(driver_name="rabbitmq", driver_config=driver_config)

    Args:
        driver_name: Type of message bus ("rabbitmq", "azureservicebus", or "noop")
        driver_config: DriverConfig instance with driver configuration.
        enable_validation: If True (default), wraps the subscriber in ValidatingEventSubscriber.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but callbacks are skipped.

    Returns:
        EventSubscriber instance (ValidatingEventSubscriber by default)

    Raises:
        ValueError: If driver_name is not recognized
        ValueError: If required parameters are missing for the specified driver
    """
    driver_name_lower = driver_name.lower()

    # Create base subscriber
    if driver_name_lower == "rabbitmq":
        from .rabbitmq_subscriber import RabbitMQSubscriber
        base_subscriber = RabbitMQSubscriber.from_config(driver_config)
    elif driver_name_lower in ("azureservicebus", "servicebus"):
        from .azureservicebussubscriber import AzureServiceBusSubscriber
        base_subscriber = AzureServiceBusSubscriber.from_config(driver_config)
    elif driver_name_lower == "noop":
        from .noop_subscriber import NoopSubscriber
        base_subscriber = NoopSubscriber.from_config(driver_config)
    else:
        raise ValueError(
            f"Unknown driver_name: {driver_name}. "
            "Supported: 'rabbitmq', 'azureservicebus', 'noop'"
        )
    
    # Wrap in validating subscriber if enabled
    if enable_validation:
        from .validating_subscriber import ValidatingEventSubscriber
        schema_provider = _get_schema_provider()
        return ValidatingEventSubscriber(
            subscriber=base_subscriber,
            schema_provider=schema_provider,
            strict=strict_validation,
        )
    
    return base_subscriber
