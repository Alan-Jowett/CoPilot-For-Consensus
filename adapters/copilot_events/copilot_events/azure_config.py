# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Service Bus configuration helper utilities."""

import os
from typing import Any


def get_azure_servicebus_kwargs() -> dict[str, Any]:
    """Get Azure Service Bus connection parameters from environment variables.

    Reads configuration from environment variables and returns a dictionary
    suitable for passing to create_publisher() or create_subscriber() when
    MESSAGE_BUS_TYPE is "azureservicebus".

    Environment Variables:
        MESSAGE_BUS_USE_MANAGED_IDENTITY: "true" to use managed identity auth
        MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE: Service Bus namespace (e.g., "mynamespace.servicebus.windows.net")
        MESSAGE_BUS_CONNECTION_STRING: Connection string (alternative to managed identity)

    Returns:
        Dictionary with Azure Service Bus configuration parameters:
        - connection_string: Connection string (if not using managed identity)
        - fully_qualified_namespace: Namespace (if using managed identity)
        - use_managed_identity: True if using managed identity

    Raises:
        ValueError: If neither connection_string nor fully_qualified_namespace is provided
    """
    use_managed_identity = os.getenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false").lower() == "true"

    if use_managed_identity:
        fully_qualified_namespace = os.getenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE")
        if not fully_qualified_namespace:
            raise ValueError(
                "MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE environment variable is required "
                "when MESSAGE_BUS_USE_MANAGED_IDENTITY is true"
            )

        return {
            "fully_qualified_namespace": fully_qualified_namespace,
            "use_managed_identity": True,
        }
    else:
        connection_string = os.getenv("MESSAGE_BUS_CONNECTION_STRING")
        if not connection_string:
            raise ValueError(
                "MESSAGE_BUS_CONNECTION_STRING environment variable is required "
                "when not using managed identity for Azure Service Bus"
            )

        return {
            "connection_string": connection_string,
        }
