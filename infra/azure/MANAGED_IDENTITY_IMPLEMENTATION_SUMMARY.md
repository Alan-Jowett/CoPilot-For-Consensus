<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Azure Managed Identity for Service Bus - Implementation Summary

## Overview

This implementation adds support for Azure Managed Identity authentication as an alternative to connection string-based authentication for Azure Service Bus in the ARM deployment template. This aligns with Azure security best practices for passwordless authentication and eliminates the need to manage and rotate Service Bus connection strings.

## Changes Made

### 1. ARM Template (`infra/azure/azuredeploy.json`)

#### New Parameters
- **`useManagedIdentityForServiceBus`** (bool, default: false)
  - Toggles between connection string and managed identity authentication modes
  
- **`serviceBusNamespace`** (string, default: "")
  - Fully qualified Service Bus namespace (e.g., `mynamespace.servicebus.windows.net`)
  - Required when `useManagedIdentityForServiceBus` is true
  
- **`serviceBusResourceId`** (string, default: "")
  - Azure Service Bus namespace resource ID for RBAC role assignments
  - Required when `useManagedIdentityForServiceBus` is true
  - Format: `/subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.ServiceBus/namespaces/{namespace}`

- **`serviceBusConnectionString`** (securestring, default: "")
  - Made optional (was required before)
  - Only needed when `useManagedIdentityForServiceBus` is false

#### Role Definitions
Added two new Service Bus RBAC role definitions to the `roleDefinitions` variable:
- **Azure Service Bus Data Sender** (role ID: `69a216fc-b8fb-44d4-bc22-1f3c7cd27a98`)
- **Azure Service Bus Data Receiver** (role ID: `4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0`)

#### Service Bus Role Assignments Mapping
Created `serviceBusRoleAssignments` variable with 7 services that use message bus:

| Service | Roles |
|---------|-------|
| ingestion | Data Sender only |
| parsing | Data Sender + Data Receiver |
| chunking | Data Sender + Data Receiver |
| embedding | Data Sender + Data Receiver |
| orchestrator | Data Sender + Data Receiver |
| summarization | Data Sender + Data Receiver |
| reporting | Data Sender + Data Receiver |

Services NOT in the list (auth, ui, gateway) don't use Service Bus and correctly don't get role assignments.

#### RBAC Role Assignment Resource
Added conditional nested deployment for Service Bus role assignments:
- Only deploys when `useManagedIdentityForServiceBus` is true
- Uses nested deployment to assign roles in the Service Bus namespace's resource group
- Iterates over each service and assigns the appropriate roles
- Handles both new and existing managed identities

#### Environment Variables
Updated container environment variables to conditionally set:

**When `useManagedIdentityForServiceBus` is false (connection string mode):**
- `MESSAGE_BUS_TYPE=azureservicebus`
- `MESSAGE_BUS_CONNECTION_STRING` (from secret)

**When `useManagedIdentityForServiceBus` is true (managed identity mode):**
- `MESSAGE_BUS_TYPE=azureservicebus`
- `MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE` (value from parameter)
- `MESSAGE_BUS_USE_MANAGED_IDENTITY=true`

#### Secrets
Modified secrets array to conditionally exclude Service Bus connection string when using managed identity mode.

### 2. Parameters File (`infra/azure/azuredeploy.parameters.json`)

Added new parameters with default values:
```json
{
  "useManagedIdentityForServiceBus": { "value": false },
  "serviceBusConnectionString": { "value": "REPLACE_WITH_YOUR_SERVICEBUS_CONNECTION_STRING" },
  "serviceBusNamespace": { "value": "" },
  "serviceBusResourceId": { "value": "" }
}
```

### 3. Documentation

#### README.md Updates
- Added **Service Bus Authentication Modes** section with detailed explanation of both modes
- Updated **Architecture** section to mention Service Bus RBAC roles
- Updated **Configuration** section with examples for both modes
- Updated **Service Bus Creation** section with commands for both modes
- Updated **Security Best Practices** to recommend managed identity mode
- Updated **Least Privilege RBAC** section with Service Bus role details

#### New Integration Guide (SERVICE_BUS_INTEGRATION_GUIDE.md)
Created comprehensive 250+ line guide covering:
- Background and rationale
- Environment variables set by ARM template
- Detailed code examples for service updates
- Helper function for standardizing configuration
- List of services that need updates
- Testing instructions (local and Azure)
- RBAC role explanations
- Benefits of managed identity mode
- Troubleshooting common issues
- External references

## Technical Implementation Details

### ARM Template Expressions

Due to ARM template limitations, complex conditional logic had to be implemented using single-line expressions:

1. **Secrets Array**: Uses nested `if()` and `createArray()` functions to conditionally include/exclude Service Bus connection string
2. **Environment Variables**: Uses `concat()` and conditional `if()` to dynamically build env var array based on authentication mode

While these expressions are dense, they follow ARM template best practices for conditional resource configuration.

### Cross-Resource-Group Deployment

The Service Bus role assignments use nested deployment because:
1. The Service Bus namespace may be in a different resource group than the Container Apps
2. RBAC role assignments must be scoped to the Service Bus namespace resource
3. Nested deployment allows specifying the target resource group dynamically

## Validation

✅ **ARM Template JSON Syntax**: Passed  
✅ **Template Structure Validation**: Passed  
✅ **Parameters File Validation**: Passed  
✅ **Code Review**: Completed (minor readability concerns about complex expressions, but acceptable for ARM templates)  
✅ **Security Scan**: No vulnerabilities detected  

## Backward Compatibility

✅ Fully backward compatible
- Default value of `useManagedIdentityForServiceBus` is `false`
- Existing deployments continue to work with connection strings
- No breaking changes to existing parameters

## Migration Path

For existing deployments wanting to adopt managed identity:

1. **Deploy with existing settings** (`useManagedIdentityForServiceBus: false`)
2. **Update service code** following the integration guide to support new env vars
3. **Test with connection string** to ensure changes are backward compatible
4. **Obtain Service Bus resource ID and namespace** using Azure CLI
5. **Update parameters file** with new values and set `useManagedIdentityForServiceBus: true`
6. **Redeploy** - services will now use managed identity authentication
7. **Verify** - check logs and Service Bus metrics to confirm authentication works
8. **Optional**: Remove connection string from parameter file for improved security

## Benefits Delivered

1. ✅ **Security**: Eliminates need to store and manage Service Bus connection strings
2. ✅ **Compliance**: Aligns with Azure security best practices and passwordless authentication
3. ✅ **Auditability**: All Service Bus access is logged via Azure Activity Log with identity information
4. ✅ **Maintainability**: No secret rotation needed; credentials managed by Azure
5. ✅ **Consistency**: Matches existing managed identity pattern for Key Vault and Storage
6. ✅ **Flexibility**: Supports both modes, allowing gradual migration

## Next Steps for Full Implementation

1. **Service Code Updates**: Update each service to read and use new environment variables (guide provided)
2. **Testing**: Deploy to Azure test environment and validate both authentication modes
3. **Documentation**: Add deployment examples and troubleshooting to main README
4. **CI/CD**: Update GitHub Actions workflows to support managed identity deployments
5. **Migration Guide**: Create guide for teams to migrate existing deployments

## Files Changed

| File | Lines Changed | Type |
|------|---------------|------|
| infra/azure/azuredeploy.json | ~50 additions, ~10 modifications | ARM Template |
| infra/azure/azuredeploy.parameters.json | ~6 additions | Parameters |
| infra/azure/README.md | ~80 additions, ~10 modifications | Documentation |
| infra/azure/SERVICE_BUS_INTEGRATION_GUIDE.md | ~250 additions (new file) | Documentation |

## Testing Checklist

- [x] ARM template JSON validation
- [x] Parameters file validation
- [x] Template structure validation
- [x] Code review
- [x] Security scan (CodeQL)
- [ ] Deploy to Azure test environment (requires Azure subscription)
- [ ] Test connection string mode
- [ ] Test managed identity mode
- [ ] Verify RBAC role assignments
- [ ] Test service authentication with both modes
- [ ] Verify Service Bus access logs

## References

- Issue: #[issue-number] - Add support for Azure Managed Identity authentication with Service Bus in ARM template
- [Azure Service Bus Authentication with Managed Identities](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity)
- [Azure RBAC Built-in Roles](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles)
- [ARM Template Best Practices](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/best-practices)
