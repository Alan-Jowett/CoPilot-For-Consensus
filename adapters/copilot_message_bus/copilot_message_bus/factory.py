# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory functions for creating message bus publishers and subscribers."""

import logging
from typing import Any, TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
    DriverConfig_MessageBus_AzureServiceBus,
    DriverConfig_MessageBus_Noop,
    DriverConfig_MessageBus_Rabbitmq,
)

from .base import EventPublisher, EventSubscriber

logger = logging.getLogger(__name__)

_DriverConfig: TypeAlias = (
    DriverConfig_MessageBus_Rabbitmq
    | DriverConfig_MessageBus_AzureServiceBus
    | DriverConfig_MessageBus_Noop
)


def _build_publisher_rabbitmq(config: _DriverConfig) -> EventPublisher:
    from .rabbitmq_publisher import RabbitMQPublisher

    if not isinstance(config, DriverConfig_MessageBus_Rabbitmq):
        raise TypeError("driver config must be DriverConfig_MessageBus_Rabbitmq")
    return RabbitMQPublisher.from_config(config)


def _build_publisher_azure_service_bus(config: _DriverConfig) -> EventPublisher:
    from .azureservicebuspublisher import AzureServiceBusPublisher

    if not isinstance(config, DriverConfig_MessageBus_AzureServiceBus):
        raise TypeError("driver config must be DriverConfig_MessageBus_AzureServiceBus")
    return AzureServiceBusPublisher.from_config(config)


def _build_publisher_noop(config: _DriverConfig) -> EventPublisher:
    from .noop_publisher import NoopPublisher

    if not isinstance(config, DriverConfig_MessageBus_Noop):
        raise TypeError("driver config must be DriverConfig_MessageBus_Noop")
    return NoopPublisher.from_config(config)


def _build_subscriber_rabbitmq(config: _DriverConfig) -> EventSubscriber:
    from .rabbitmq_subscriber import RabbitMQSubscriber

    if not isinstance(config, DriverConfig_MessageBus_Rabbitmq):
        raise TypeError("driver config must be DriverConfig_MessageBus_Rabbitmq")
    return RabbitMQSubscriber.from_config(config)


def _build_subscriber_azure_service_bus(config: _DriverConfig) -> EventSubscriber:
    from .azureservicebussubscriber import AzureServiceBusSubscriber

    if not isinstance(config, DriverConfig_MessageBus_AzureServiceBus):
        raise TypeError("driver config must be DriverConfig_MessageBus_AzureServiceBus")
    return AzureServiceBusSubscriber.from_config(config)


def _build_subscriber_noop(config: _DriverConfig) -> EventSubscriber:
    from .noop_subscriber import NoopSubscriber

    if not isinstance(config, DriverConfig_MessageBus_Noop):
        raise TypeError("driver config must be DriverConfig_MessageBus_Noop")
    return NoopSubscriber.from_config(config)


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
    config: AdapterConfig_MessageBus,
    enable_validation: bool = True,
    strict_validation: bool = True,
) -> EventPublisher:
    """Factory function to create an event publisher.

    By default, returns a validating publisher that enforces schema validation.
    This ensures all events are validated before being published.

    Usage:
        create_publisher(config)

    Args:
        config: Typed AdapterConfig_MessageBus instance.
        enable_validation: If True (default), wraps the publisher in ValidatingEventPublisher.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but publishing proceeds.

    Returns:
        EventPublisher instance (ValidatingEventPublisher by default)

    Raises:
        ValueError: If config is missing or driver type is unknown
        ValueError: If required parameters are missing for the specified driver
    """
    base_publisher = create_adapter(
        config,
        adapter_name="message_bus",
        get_driver_type=lambda c: c.message_bus_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "rabbitmq": _build_publisher_rabbitmq,
            "azure_service_bus": _build_publisher_azure_service_bus,
            "noop": _build_publisher_noop,
        },
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
    config: AdapterConfig_MessageBus,
    enable_validation: bool = True,
    strict_validation: bool = True,
) -> EventSubscriber:
    """Factory function to create an event subscriber.

    By default, returns a validating subscriber that enforces schema validation.
    This ensures all received events are validated before being passed to callbacks.

    Usage:
        create_subscriber(config)

    Args:
        config: Typed AdapterConfig_MessageBus instance.
        enable_validation: If True (default), wraps the subscriber in ValidatingEventSubscriber.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but callbacks are skipped.

    Returns:
        EventSubscriber instance (ValidatingEventSubscriber by default)

    Raises:
        ValueError: If config is missing or driver type is unknown
        ValueError: If required parameters are missing for the specified driver
    """
    base_subscriber = create_adapter(
        config,
        adapter_name="message_bus",
        get_driver_type=lambda c: c.message_bus_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "rabbitmq": _build_subscriber_rabbitmq,
            "azure_service_bus": _build_subscriber_azure_service_bus,
            "noop": _build_subscriber_noop,
        },
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
