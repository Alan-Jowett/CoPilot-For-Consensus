// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Azure Key Vault and assign managed identity access policies'

param location string
param keyVaultName string
param tenantId string
param managedIdentityPrincipalIds array
param enablePublicNetworkAccess bool = true
param enableRbacAuthorization bool = false  // Set to true to use Azure RBAC instead of access policies
param tags object

// Create Azure Key Vault
// Authorization approach:
// - enableRbacAuthorization = false (default): Uses legacy access policies for backward compatibility
// - enableRbacAuthorization = true: Uses modern Azure RBAC with role assignments (recommended)
//
// Migration strategy:
// PR #1 (foundation): Uses access policies as fallback for quick validation
// PR #2-5 (services): Each new service will use Azure RBAC 'Key Vault Secrets User' role assignments
// Future: Remove accessPolicies array when all services migrated to RBAC
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: enableRbacAuthorization ? [] : accessPoliciesArray  // Empty if using RBAC, populated if using legacy access policies
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: enablePublicNetworkAccess ? null : {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    enableRbacAuthorization: enableRbacAuthorization
  }
}

// Build access policies array from principal IDs array
// Used only when enableRbacAuthorization = false (legacy mode)
// Note: This approach allows 'list' permission for secret enumeration; can be removed once
// all services migrate to Azure RBAC 'Key Vault Secrets User' role in future PRs
var accessPoliciesArray = [
  for principalId in managedIdentityPrincipalIds: {
    objectId: principalId
    tenantId: tenantId
    permissions: {
      secrets: [
        'get'
        'list'  // WARNING: 'list' allows enumeration of all secrets; removed when migrating to RBAC role assignments
      ]
      keys: []
      certificates: []
    }
  }
]

// Add access policies to grant secret read permissions to each service identity (legacy approach)
// Only deployed when enableRbacAuthorization = false
// Future PRs will replace this with Azure RBAC role assignments (Key Vault Secrets User)
// which provides better integration with Azure AD and more granular control
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = if (!enableRbacAuthorization) {
  name: 'add'
  parent: keyVault
  properties: {
    accessPolicies: accessPoliciesArray
  }
}

// Outputs
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
