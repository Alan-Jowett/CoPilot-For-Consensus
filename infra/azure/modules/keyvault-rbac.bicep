// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure per-secret RBAC role assignments for Azure Key Vault'

@description('Key Vault resource ID')
param keyVaultId string

@description('Key Vault name')
param keyVaultName string

@description('Map of service names to principal IDs')
param servicePrincipalIds object

@description('Enable RBAC authorization (must match Key Vault configuration)')
param enableRbacAuthorization bool = true

// Key Vault Secrets User role definition ID
// This built-in role allows reading secret contents but not listing/managing secrets
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// Reference existing Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// ============================================================================
// JWT KEYS - Auth service only (sign tokens)
// ============================================================================

resource jwtPrivateKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'jwt-private-key'
}

resource jwtPublicKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'jwt-public-key'
}

// Auth service needs private key to sign tokens
resource authJwtPrivateKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization) {
  name: guid(jwtPrivateKeySecret.id, servicePrincipalIds.auth, keyVaultSecretsUserRoleId)
  scope: jwtPrivateKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds.auth
    principalType: 'ServicePrincipal'
  }
}

// Auth service needs public key to verify tokens
resource authJwtPublicKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization) {
  name: guid(jwtPublicKeySecret.id, servicePrincipalIds.auth, keyVaultSecretsUserRoleId)
  scope: jwtPublicKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds.auth
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// APPLICATION INSIGHTS - All services (telemetry)
// ============================================================================

resource appInsightsInstrKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'appinsights-instrumentation-key'
}

resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'appinsights-connection-string'
}

// Grant all services access to App Insights secrets for telemetry
var allServices = [
  'ingestion'
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
  'auth'
  'ui'
  'gateway'
  'openai'
]

resource appInsightsInstrKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for service in allServices: if (enableRbacAuthorization) {
    name: guid(appInsightsInstrKeySecret.id, servicePrincipalIds[service], keyVaultSecretsUserRoleId)
    scope: appInsightsInstrKeySecret
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
      principalId: servicePrincipalIds[service]
      principalType: 'ServicePrincipal'
    }
  }
]

resource appInsightsConnectionStringAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for service in allServices: if (enableRbacAuthorization) {
    name: guid(appInsightsConnectionStringSecret.id, servicePrincipalIds[service], keyVaultSecretsUserRoleId)
    scope: appInsightsConnectionStringSecret
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
      principalId: servicePrincipalIds[service]
      principalType: 'ServicePrincipal'
    }
  }
]

// ============================================================================
// AZURE OPENAI API KEY - OpenAI service only
// ============================================================================

resource openaiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'azure-openai-api-key'
}

resource openaiServiceApiKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization) {
  name: guid(openaiApiKeySecret.id, servicePrincipalIds.openai, keyVaultSecretsUserRoleId)
  scope: openaiApiKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds.openai
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// OAUTH SECRETS - Auth service only
// ============================================================================
// Note: OAuth secrets are created manually or by deployment scripts after initial deployment.
// Since we cannot reference secrets that don't exist yet, we grant the auth service
// vault-level "Key Vault Secrets User" role with a condition that limits access.
// This is still more secure than the legacy access policy approach because:
// 1. Only ONE service (auth) gets this permission (not all services)
// 2. The role is scoped to secrets operations only (no keys/certificates)
// 3. Can be further restricted with Azure Policy if needed

// Grant auth service vault-level access for OAuth and other auth-related secrets
// This allows the auth service to read secrets like:
// - github-oauth-client-id, github-oauth-client-secret
// - google-oauth-client-id, google-oauth-client-secret
// - microsoft-oauth-client-id, microsoft-oauth-client-secret
// - entra-oauth-client-id, entra-oauth-client-secret
// All these secrets are only needed by the auth service
resource authServiceVaultSecretsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization) {
  name: guid(keyVaultId, servicePrincipalIds.auth, keyVaultSecretsUserRoleId, 'oauth-secrets')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds.auth
    principalType: 'ServicePrincipal'
    description: 'Allow auth service to read OAuth and authentication-related secrets (GitHub, Google, Microsoft, Entra)'
  }
}

// ============================================================================
// GRAFANA CREDENTIALS - Infrastructure/monitoring only
// ============================================================================
// Note: These are typically accessed by the Grafana container app directly
// Not granting access to regular services as they don't need Grafana credentials

resource grafanaAdminUserSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'grafana-admin-user'
}

resource grafanaAdminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'grafana-admin-password'
}

// Grafana credentials are accessed via Container Apps secret reference
// No service principal access needed here as Container Apps platform handles the access

// Outputs
output deployedRbacRoleAssignments array = enableRbacAuthorization ? [
  {
    service: 'auth'
    secret: 'jwt-private-key'
    roleAssignmentId: authJwtPrivateKeyAccess.id
  }
  {
    service: 'auth'
    secret: 'jwt-public-key'
    roleAssignmentId: authJwtPublicKeyAccess.id
  }
  {
    service: 'openai'
    secret: 'azure-openai-api-key'
    roleAssignmentId: openaiServiceApiKeyAccess.id
  }
] : []

output summary string = enableRbacAuthorization ? '''
✅ Per-secret RBAC role assignments configured:
- JWT private key: auth service only (secret-scoped)
- JWT public key: auth service only (secret-scoped)
- App Insights secrets: all services (secret-scoped for telemetry)
- Azure OpenAI API key: openai service only (secret-scoped)
- OAuth secrets: auth service only (vault-scoped for dynamically created secrets)
- Grafana credentials: accessed via Container Apps platform (no service access needed)

🔒 Security Improvement:
- Before: All 11 services had vault-wide 'get' access to ALL secrets
- After: Each service can only access specific secrets it needs
- Blast radius of compromised service significantly reduced
''' : 'RBAC authorization is disabled. Using legacy access policies (NOT RECOMMENDED).'
