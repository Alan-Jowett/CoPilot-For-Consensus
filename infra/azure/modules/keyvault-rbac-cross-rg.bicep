// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Cross-RG RBAC module to grant env identities access to Core Key Vault'

@description('Core Key Vault name')
param keyVaultName string

@description('Array of env service principal IDs that need access to Core Key Vault')
param envServicePrincipalIds array

// Built-in role: Key Vault Secrets User (read-only access to secret values)
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource coreKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Grant each env service identity access to read secrets from Core Key Vault
resource coreKvRbacAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in envServicePrincipalIds: {
    name: guid(coreKeyVault.id, principalId, keyVaultSecretsUserRoleId)
    scope: coreKeyVault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
      principalId: principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output summary string = 'Granted Key Vault Secrets User role to ${length(envServicePrincipalIds)} env service identities on Core Key Vault ${keyVaultName}'
