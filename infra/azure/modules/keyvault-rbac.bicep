// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure per-secret RBAC role assignments for Azure Key Vault'

@description('Key Vault name')
param keyVaultName string

@description('Map of service names to principal IDs')
param servicePrincipalIds object

@description('Enable RBAC authorization (must match Key Vault configuration)')
param enableRbacAuthorization bool = true

@description('Whether Azure OpenAI is deployed (controls OpenAI secret access assignments)')
param deployAzureOpenAI bool = true

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
resource authJwtPrivateKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization && contains(servicePrincipalIds, 'auth')) {
  name: guid(jwtPrivateKeySecret.id, servicePrincipalIds['auth'], keyVaultSecretsUserRoleId)
  scope: jwtPrivateKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds['auth']
    principalType: 'ServicePrincipal'
  }
}

// Auth service needs public key to verify tokens
resource authJwtPublicKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization && contains(servicePrincipalIds, 'auth')) {
  name: guid(jwtPublicKeySecret.id, servicePrincipalIds['auth'], keyVaultSecretsUserRoleId)
  scope: jwtPublicKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds['auth']
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
// Derive service list from servicePrincipalIds parameter to avoid desynchronization
var allServices = [for serviceItem in items(servicePrincipalIds): serviceItem.key]

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

resource openaiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = if (deployAzureOpenAI) {
  parent: keyVault
  name: 'azure-openai-api-key'
}

resource openaiServiceApiKeyAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableRbacAuthorization && deployAzureOpenAI && contains(servicePrincipalIds, 'openai')) {
  name: guid(openaiApiKeySecret.id, servicePrincipalIds['openai'], keyVaultSecretsUserRoleId)
  scope: openaiApiKeySecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: servicePrincipalIds['openai']
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// OAUTH SECRETS - Auth service only
// ============================================================================
// IMPORTANT SECURITY LIMITATION:
// OAuth secrets (github-oauth-*, google-oauth-*, microsoft-oauth-*, entra-oauth-*)
// are created manually or by deployment scripts AFTER initial infrastructure deployment.
// Because these secrets don't exist at deployment time, we cannot create secret-scoped
// role assignments for them in this module.
//
// WORKAROUND OPTIONS:
// 1. Create placeholder OAuth secrets during initial deployment (set to empty/dummy values)
//    and add secret-scoped role assignments here
// 2. Manually grant auth service access to OAuth secrets after they're created via Azure Portal
// 3. Use a separate deployment script that creates OAuth secrets AND their role assignments
//
// CURRENT APPROACH: Users must manually create OAuth secrets and configure access.
// This maintains least-privilege as auth service has NO default vault-wide access.
// See KEYVAULT_RBAC.md for instructions on configuring OAuth secret access post-deployment.
//
// To grant auth service access to a specific OAuth secret after creation:
//   az role assignment create \
//     --assignee <auth-service-principal-id> \
//     --role "Key Vault Secrets User" \
//     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault>/secrets/<secret-name>

// ============================================================================
// GRAFANA CREDENTIALS - Infrastructure/monitoring only
// ============================================================================
// Note: Grafana credentials are accessed directly by Container Apps platform
// via secret references in the container app configuration. No service principal
// access is needed, so no role assignments are created here.
// The secrets are declared in main.bicep and referenced by the Grafana container app.

// Outputs
output deployedRbacRoleAssignments array = enableRbacAuthorization ? concat(
  // JWT key assignments
  contains(servicePrincipalIds, 'auth') ? [
    {
      service: 'auth'
      secret: 'jwt-private-key'
      scope: 'secret'
      roleAssignmentId: authJwtPrivateKeyAccess.id
    }
    {
      service: 'auth'
      secret: 'jwt-public-key'
      scope: 'secret'
      roleAssignmentId: authJwtPublicKeyAccess.id
    }
  ] : [],
  // OpenAI key assignment
  (deployAzureOpenAI && contains(servicePrincipalIds, 'openai')) ? [
    {
      service: 'openai'
      secret: 'azure-openai-api-key'
      scope: 'secret'
      roleAssignmentId: openaiServiceApiKeyAccess.id
    }
  ] : [],
  // App Insights assignments summary (not listing all 22 individual assignments)
  [
    {
      service: 'all-services'
      secret: 'appinsights-instrumentation-key'
      scope: 'secret'
      roleAssignmentId: 'multiple (${length(allServices)} services)'
    }
    {
      service: 'all-services'
      secret: 'appinsights-connection-string'
      scope: 'secret'
      roleAssignmentId: 'multiple (${length(allServices)} services)'
    }
  ]
) : []

output summary string = enableRbacAuthorization ? '''
✅ Per-secret RBAC role assignments configured:
- JWT private key: auth service only (secret-scoped)
- JWT public key: auth service only (secret-scoped)
- App Insights secrets: all ${length(allServices)} services (secret-scoped for telemetry)
${deployAzureOpenAI ? '- Azure OpenAI API key: openai service only (secret-scoped)' : '- Azure OpenAI: not deployed, no assignments created'}
- OAuth secrets: NOT CONFIGURED - must be manually assigned post-deployment (see KEYVAULT_RBAC.md)
- Grafana credentials: accessed via Container Apps platform (no service access needed)

🔒 Security Improvement:
- Before: All ${length(allServices)} services had vault-wide 'get' access to ALL secrets
- After: Each service can only access specific secrets it needs
- Blast radius of compromised service significantly reduced

⚠️  IMPORTANT: OAuth secrets require manual RBAC configuration after creation.
   See KEYVAULT_RBAC.md for post-deployment OAuth secret access setup instructions.
''' : 'RBAC authorization is disabled. Using legacy access policies (NOT RECOMMENDED).'
