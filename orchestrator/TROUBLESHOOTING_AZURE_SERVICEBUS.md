# Troubleshooting Azure Service Bus Authentication Errors

This guide helps diagnose and resolve Azure Service Bus authentication errors in the Orchestrator service.

## Common Error

```
azure.servicebus.exceptions.ServiceBusAuthenticationError: Service Bus has encountered an error. Error condition: amqp:client-error.
```

## Root Causes

This error typically occurs due to one of the following issues:

### 1. Missing or Incorrect Environment Variables

**For Managed Identity Mode (Recommended for Azure deployments):**

Required environment variables:
- `MESSAGE_BUS_TYPE=azureservicebus`
- `MESSAGE_BUS_USE_MANAGED_IDENTITY=true`
- `MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE=<namespace>.servicebus.windows.net`

**For Connection String Mode (Local development or legacy deployments):**

Required environment variables:
- `MESSAGE_BUS_TYPE=azureservicebus`
- `MESSAGE_BUS_USE_MANAGED_IDENTITY=false` (or omit this variable)
- `MESSAGE_BUS_CONNECTION_STRING=Endpoint=sb://...`

**Verification:**
```bash
# Check environment variables in the running container
docker exec <container-id> env | grep MESSAGE_BUS

# Or for Azure Container Apps
az containerapp show --name orchestrator --resource-group <rg> --query properties.template.containers[0].env
```

### 2. Missing RBAC Role Assignments

The orchestrator managed identity must have both roles assigned:
- **Azure Service Bus Data Sender** - to publish `summarization.requested` events
- **Azure Service Bus Data Receiver** - to consume `embeddings.generated` events

**Verification:**
```bash
# List role assignments for the orchestrator managed identity
az role assignment list \
  --assignee <orchestrator-managed-identity-principal-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ServiceBus/namespaces/<namespace>
```

Expected output should include:
- `Azure Service Bus Data Sender` role
- `Azure Service Bus Data Receiver` role

**Fix:**
```bash
# Get the orchestrator managed identity principal ID
ORCHESTRATOR_PRINCIPAL_ID=$(az identity show \
  --name copilot-dev-orchestrator-id \
  --resource-group cfc-dev-rg \
  --query principalId -o tsv)

# Get the Service Bus namespace resource ID
SERVICEBUS_ID=$(az servicebus namespace show \
  --name copilot-sb-dev-ej3rgjyh \
  --resource-group cfc-dev-rg \
  --query id -o tsv)

# Assign Data Sender role
az role assignment create \
  --role "Azure Service Bus Data Sender" \
  --assignee $ORCHESTRATOR_PRINCIPAL_ID \
  --scope $SERVICEBUS_ID

# Assign Data Receiver role
az role assignment create \
  --role "Azure Service Bus Data Receiver" \
  --assignee $ORCHESTRATOR_PRINCIPAL_ID \
  --scope $SERVICEBUS_ID
```

**Note:** Role assignments can take up to 5 minutes to propagate. Wait before retesting.

### 3. RBAC Propagation Delay

Azure RBAC role assignments are not instantaneous. After assigning roles:
- Wait 2-5 minutes for propagation
- Restart the orchestrator service
- Check logs for successful connection

### 4. Queue Does Not Exist or Cannot Be Created

The orchestrator dynamically creates a queue named `orchestrator-service` on startup. Unlike the routing queues (e.g., `embeddings.generated`, `summarization.requested`) which are pre-created by the infrastructure, service-specific queues are created by the services themselves.

For Azure Service Bus, the managed identity needs **Azure Service Bus Data Owner** role or explicit queue creation permissions in addition to Send/Receive permissions to auto-create queues.

**Verification:**
```bash
# List queues in the Service Bus namespace
az servicebus queue list \
  --namespace-name copilot-sb-dev-ej3rgjyh \
  --resource-group cfc-dev-rg \
  --query "[].name"
```

**Fix Option 1: Pre-create the queue (recommended for production)**
```bash
# Create the orchestrator-service queue before starting the service
az servicebus queue create \
  --name orchestrator-service \
  --namespace-name copilot-sb-dev-ej3rgjyh \
  --resource-group cfc-dev-rg \
  --max-delivery-count 10 \
  --lock-duration PT5M
```

**Fix Option 2: Grant queue creation permissions**
```bash
# Assign Data Owner role (includes queue creation)
az role assignment create \
  --role "Azure Service Bus Data Owner" \
  --assignee $ORCHESTRATOR_PRINCIPAL_ID \
  --scope $SERVICEBUS_ID
```

**Note:** The routing queues (`embeddings.generated`, `summarization.requested`, etc.) are already created by the Bicep infrastructure and do not need manual creation. Only the `orchestrator-service` queue needs to exist or the managed identity needs creation permissions.

### 5. Malformed Connection String

If using connection string mode, ensure the connection string:
- Starts with `Endpoint=sb://`
- Includes `SharedAccessKeyName` and `SharedAccessKey`
- Is for the correct namespace
- Has permissions for Send and Listen operations

**Verification:**
```bash
# Test connection string format (replace with your actual connection string)
echo "Endpoint=sb://copilot-sb-dev-ej3rgjyh.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=..." | grep -o "Endpoint=sb://[^/]*"
```

### 6. Managed Identity Not Enabled for Container App

The Container App must have a system-assigned or user-assigned managed identity enabled.

**Verification:**
```bash
# Check if managed identity is enabled
az containerapp show \
  --name orchestrator \
  --resource-group cfc-dev-rg \
  --query identity
```

**Fix:**
```bash
# Enable system-assigned managed identity
az containerapp identity assign \
  --name orchestrator \
  --resource-group cfc-dev-rg \
  --system-assigned
```

## Diagnostic Steps

### Step 1: Check Service Logs

```bash
# For Docker Compose
docker logs orchestrator

# For Azure Container Apps
az containerapp logs show \
  --name orchestrator \
  --resource-group cfc-dev-rg \
  --follow
```

Look for:
- "Using Azure Service Bus configuration" (indicates Azure Service Bus mode is active)
- "Using Azure Service Bus with managed identity" or "Using Azure Service Bus with connection string"
- Connection errors or authentication errors

### Step 2: Verify Infrastructure Deployment

```bash
# Check if the Bicep template was deployed with managed identity enabled
az deployment group show \
  --name <deployment-name> \
  --resource-group cfc-dev-rg \
  --query properties.parameters.useManagedIdentityForServiceBus.value
```

Should return `true` if using managed identity mode.

### Step 3: Test Azure Service Bus Connection

Use the Azure Service Bus Explorer or Azure Portal to verify:
1. The namespace is accessible
2. The queue `orchestrator-service` exists
3. The managed identity has the correct permissions

### Step 4: Redeploy Infrastructure

If the infrastructure was deployed without managed identity support, redeploy with:

```bash
cd infra/azure
az deployment group create \
  --resource-group cfc-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters useManagedIdentityForServiceBus=true \
  --parameters serviceBusNamespace=copilot-sb-dev-ej3rgjyh.servicebus.windows.net \
  --parameters serviceBusResourceId=/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ServiceBus/namespaces/copilot-sb-dev-ej3rgjyh
```

## Prevention

To prevent this issue in the future:

1. **Always deploy with managed identity enabled** for production environments
2. **Use the deployment script** that validates all prerequisites
3. **Run integration tests** after deployment to verify connectivity
4. **Document environment variables** in deployment runbooks
5. **Monitor role assignment propagation** before marking deployment as complete

## Related Documentation

- [Azure Service Bus Integration Guide](../infra/azure/SERVICE_BUS_INTEGRATION_GUIDE.md)
- [Managed Identity Implementation Summary](../infra/azure/MANAGED_IDENTITY_IMPLEMENTATION_SUMMARY.md)
- [Queues and Events Architecture](../docs/architecture/queues-and-events.md)

## Support

If the issue persists after following these steps:

1. Check the GitHub Issues for similar reports
2. Verify the Bicep templates include `orchestrator` in `senderServices` and `receiverServices`
3. Check that `get_azure_servicebus_kwargs()` is called in `orchestrator/main.py`
4. Open a new issue with:
   - Service logs
   - Environment variables (redact secrets)
   - Role assignment output
   - Queue list output
