<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Service Bus Managed Identity Integration Guide

This guide explains how services authenticate to Azure Service Bus using managed identity, and how the deployment config maps into the `azure_service_bus` driver.

## Background

The Azure Service Bus publisher and subscriber classes (`AzureServiceBusPublisher` and `AzureServiceBusSubscriber` in `adapters/copilot_message_bus`) support managed identity authentication using `DefaultAzureCredential`.

1. **Connection String Mode**: Uses `SERVICEBUS_CONNECTION_STRING` (or `MESSAGE_BUS_CONNECTION_STRING`)
2. **Managed Identity Mode** (recommended): Uses `SERVICEBUS_FULLY_QUALIFIED_NAMESPACE` and `SERVICEBUS_USE_MANAGED_IDENTITY=true`

## Environment Variables Set by ARM Template

Azure deployments in this repo typically set:

- `MESSAGE_BUS_TYPE=azure_service_bus`
- `SERVICEBUS_USE_MANAGED_IDENTITY=true`
- `SERVICEBUS_FULLY_QUALIFIED_NAMESPACE=<namespace>.servicebus.windows.net`

Connection strings are supported by the driver for non-Azure scenarios, but the Azure Container Apps deployment is designed around managed identity.

## Service Code Updates Required

Services do not need to manually parse these environment variables. They are loaded via the schema-driven config system and passed into `create_publisher` / `create_subscriber`.

For Azure Service Bus, the deployment provisions a shared topic (`copilot.events`) plus a subscription per service. Services set `topic_name="copilot.events"` and `subscription_name=<service>` in code as service-owned constants.

### Example: How Services Select Topic/Subscription

Service `main.py` files typically do something like:

- For RabbitMQ: set a durable `queue_name` per service input
- For Azure Service Bus: set `topic_name="copilot.events"` and `subscription_name=<service_name>`

### Simplified Helper Function

You can create a helper function to standardize this across all services:

```python
def get_message_bus_kwargs(message_bus_type: str) -> dict:
    """Get message bus connection parameters based on type and environment variables.

    Args:
        message_bus_type: Type of message bus (e.g., 'azureservicebus', 'rabbitmq')

    Returns:
        Dictionary of connection parameters for the create_publisher/create_subscriber factories
    """
    if message_bus_type != "azureservicebus":
        return {}

    use_managed_identity = os.getenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false").lower() == "true"

    if use_managed_identity:
        fully_qualified_namespace = os.getenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE")
        if not fully_qualified_namespace:
            raise ValueError("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE is required when using managed identity")

        return {
            "fully_qualified_namespace": fully_qualified_namespace,
            "use_managed_identity": True,
        }
    else:
        connection_string = os.getenv("MESSAGE_BUS_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("MESSAGE_BUS_CONNECTION_STRING is required when not using managed identity")

        return {
            "connection_string": connection_string,
        }

# Usage:
message_bus_kwargs = get_message_bus_kwargs(config.message_bus_type)
publisher = create_publisher(
    message_bus_type=config.message_bus_type,
    host=config.message_bus_host,
    port=config.message_bus_port,
    username=config.message_bus_user,
    password=config.message_bus_password,
    queue_name="my-queue",  # Specify queue or topic
    **message_bus_kwargs
)
```

## Services That Need Updates

The following services use the message bus:

1. **ingestion** (`ingestion/main.py`) - Producer only

2. **parsing** (`parsing/main.py`) - Consumer + Producer

3. **chunking** (`chunking/main.py`) - Consumer + Producer
   - Needs: `queue_name` parameter for subscriber

4. **embedding** (`embedding/main.py`) - Consumer + Producer
   - Needs: `queue_name` parameter for subscriber

5. **orchestrator** (`orchestrator/main.py`) - Consumer + Producer
   - Needs: `queue_name` or `topic_name` parameter

6. **summarization** (`summarization/main.py`) - Consumer + Producer
   - Needs: `queue_name` parameter for subscriber

7. **reporting** (`reporting/main.py`) - Consumer + Producer
   - Needs: `queue_name` parameter for subscriber

## Testing

### Local Testing with Managed Identity Simulation

To test managed identity mode locally:

```bash
# Set environment variables
export MESSAGE_BUS_TYPE=azure_service_bus
export SERVICEBUS_USE_MANAGED_IDENTITY=true
export SERVICEBUS_FULLY_QUALIFIED_NAMESPACE=mynamespace.servicebus.windows.net

# Use Azure CLI to authenticate (DefaultAzureCredential will use this)
az login

# Run the service
python parsing/main.py
```

### Azure Testing

When deployed via the ARM template with `useManagedIdentityForServiceBus: true`:
1. The Container App's managed identity is automatically used
2. RBAC roles are automatically assigned
3. No additional configuration needed

## RBAC Roles

The infrastructure assigns these roles to service identities:

- **Azure Service Bus Data Sender** (for producers)
  - Role ID: `69a216fc-b8fb-44d4-bc22-1f3c7cd27a98`
  - Services: ingestion, parsing, chunking, embedding, orchestrator, summarization, reporting

- **Azure Service Bus Data Receiver** (for consumers)
  - Role ID: `4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0`
  - Services: parsing, chunking, embedding, orchestrator, summarization, reporting

## Benefits of Managed Identity Mode

1. **No secrets to manage**: Connection strings are not needed
2. **Automatic credential rotation**: Azure handles credential lifecycle
3. **Audit trail**: All access is logged via Azure Activity Log
4. **Least privilege**: RBAC roles provide fine-grained access control
5. **Simplified deployment**: No need to distribute or rotate connection strings

## Troubleshooting

### Error: "MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE is required"

**Cause**: Service is configured to use managed identity but the namespace isn't set.

**Solution**: Ensure the ARM template parameter `serviceBusNamespace` is set correctly (e.g., `mynamespace.servicebus.windows.net`).

### Error: "DefaultAzureCredential failed to retrieve a token"

**Cause**: Managed identity doesn't have permission to access Service Bus.

**Solution**:
1. Verify the Container App has a managed identity assigned
2. Check that RBAC roles are assigned to the identity on the Service Bus namespace
3. Review Azure Activity Logs for authorization failures

### Error: "Connection refused" or timeout

**Cause**: Network connectivity issue between Container App and Service Bus.

**Solution**:
1. Verify Service Bus namespace is accessible from the Container Apps VNet
2. Check firewall rules on the Service Bus namespace
3. Consider using private endpoints for production

## References

- [Azure Service Bus Authentication with Managed Identities](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity)
- [DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential)
- [Azure RBAC Built-in Roles for Service Bus](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#azure-service-bus-data-owner)
