// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Azure Key Vault and assign managed identity access policies'

param location string
param keyVaultName string
param tenantId string
param managedIdentityPrincipalIds array
param secretWriterPrincipalIds array = []
param enablePublicNetworkAccess bool = true
@description('Enable Azure RBAC authorization for Key Vault. Default is false for backward compatibility with existing deployments, but true is STRONGLY RECOMMENDED for production (see security warnings below).')
param enableRbacAuthorization bool = false
param tags object

// Built-in role IDs
// Key Vault Secrets Officer: allows write/read of secrets without full admin
var keyVaultSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

// ⚠️ SECURITY WARNING: Legacy access policy mode (enableRbacAuthorization=false)
// When RBAC is disabled, all managed identities receive vault-wide 'get' permission.
// While 'list' is disabled (preventing enumeration), services can still read ANY secret
// if they know its name. This violates least-privilege principles.
//
// ✅ RECOMMENDED: Enable RBAC mode (enableRbacAuthorization=true)
// RBAC mode combined with the keyvault-rbac module provides per-secret access control:
// - Each service only gets access to the specific secrets it needs
// - Auth service: JWT keys + OAuth secrets only
// - OpenAI service: OpenAI API key only
// - All services: App Insights secrets (telemetry)
// - Significantly reduces lateral movement risk from a compromised service
//
// Migration: Set enableRbacAuthorization=true and deploy keyvault-rbac module

// Build access policies array from principal IDs array
// Used only when enableRbacAuthorization = false (legacy mode)
// ⚠️ SECURITY LIMITATION: Vault-wide 'get' permission allows reading ANY secret by name
var readAccessPolicies = [
  for principalId in managedIdentityPrincipalIds: {
    objectId: principalId
    tenantId: tenantId
    permissions: {
      secrets: [
        'get'  // ⚠️ Can read ANY secret by name (vault-wide permission)
      ]
      keys: []
      certificates: []
    }
  }
]

var writeAccessPolicies = [
  for principalId in secretWriterPrincipalIds: {
    objectId: principalId
    tenantId: tenantId
    permissions: {
      secrets: [
        'get'  // Read access to verify written secrets
        'set'  // Write access for deployment scripts (e.g., JWT key generation)
      ]
      keys: []
      certificates: []
    }
  }
]

var combinedAccessPolicies = concat(readAccessPolicies, writeAccessPolicies)

// Create Azure Key Vault
// Authorization approach:
// - enableRbacAuthorization = false (default): Uses legacy access policies (NOT RECOMMENDED for production)
//   · Grants vault-wide 'get' permission to all services (can read any secret by name)
//   · High lateral movement risk if any service is compromised
// - enableRbacAuthorization = true: Uses modern Azure RBAC with per-secret role assignments (RECOMMENDED)
//   · Requires keyvault-rbac module to configure per-secret access
//   · Each service only gets access to specific secrets it needs
//   · Significantly improved security posture
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
    accessPolicies: enableRbacAuthorization ? [] : combinedAccessPolicies  // Empty if using RBAC, populated if using legacy access policies
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: enablePublicNetworkAccess ? null : {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    enableRbacAuthorization: enableRbacAuthorization
  }
}

// RBAC role assignments for write access (used by deployment scripts when enableRbacAuthorization = true)
resource secretWriterRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in secretWriterPrincipalIds: if (enableRbacAuthorization) {
    name: guid(keyVault.id, principalId, keyVaultSecretsOfficerRoleId)
    scope: keyVault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsOfficerRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

// Legacy access policies (only deployed when RBAC is disabled)
// ⚠️ SECURITY WARNING: Grants vault-wide 'get' permission to all services
// Use RBAC mode + keyvault-rbac module for per-secret access control instead
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = if (!enableRbacAuthorization) {
  name: 'add'
  parent: keyVault
  properties: {
    accessPolicies: combinedAccessPolicies
  }
}

// Outputs
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
