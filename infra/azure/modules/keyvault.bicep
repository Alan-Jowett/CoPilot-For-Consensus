// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Azure Key Vault and assign managed identity access policies'

param location string
param keyVaultName string
param tenantId string
param managedIdentityPrincipalIds array
param tags object

// Create Azure Key Vault
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
    accessPolicies: []
    publicNetworkAccess: 'Enabled'
  }
}

// Build access policies array from principal IDs object
var accessPoliciesArray = [
  for principalId in managedIdentityPrincipalIds: {
    objectId: principalId
    tenantId: tenantId
    permissions: {
      secrets: [
        'get'
        'list'
      ]
      keys: []
      certificates: []
    }
  }
]

// Assign Key Vault Secrets User role to each service identity
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = {
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
