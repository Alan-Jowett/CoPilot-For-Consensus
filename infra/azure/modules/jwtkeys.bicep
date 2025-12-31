// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Generate per-deployment JWT keypair and store in Key Vault via deployment script'

@description('Location for resources')
param location string

@description('Azure Key Vault name to store JWT secrets')
param keyVaultName string

@description('User-assigned managed identity resource ID used to set secrets')
param scriptIdentityId string

@description('Force tag to rerun the key generation script each deployment')
param forceUpdateTag string

@description('Secret name for the JWT private key')
param jwtPrivateSecretName string = 'jwt-private-key'

@description('Secret name for the JWT public key')
param jwtPublicSecretName string = 'jwt-public-key'

param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Deployment script generates a fresh RSA keypair and stores both private/public in Key Vault.
resource jwtKeyScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'generate-jwt-keys'
  location: location
  tags: tags
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${scriptIdentityId}': {}
    }
  }
  properties: {
    azCliVersion: '2.61.0'
    timeout: 'PT15M'
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    // Force regeneration on each deployment to meet "per-deployment" requirement
    forceUpdateTag: forceUpdateTag
    environmentVariables: [
      {
        name: 'KEY_VAULT_NAME'
        value: keyVaultName
      }
      {
        name: 'JWT_PRIVATE_SECRET_NAME'
        value: jwtPrivateSecretName
      }
      {
        name: 'JWT_PUBLIC_SECRET_NAME'
        value: jwtPublicSecretName
      }
    ]
    scriptContent: '''
set -euo pipefail
# Install openssl (not included in Azure CLI container by default)
# Try apk (Alpine) first, fallback to apt-get (Debian/Ubuntu)
(apk add --no-cache openssl 2>/dev/null || apt-get update -qq && apt-get install -y -qq openssl 2>/dev/null) || true
az login --identity --allow-no-subscriptions 2>&1 | grep -v "WARNING" || true
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
priv="$workdir/jwt_private.pem"
pub="$workdir/jwt_public.pem"
openssl genrsa -out "$priv" 2048
openssl rsa -in "$priv" -pubout -out "$pub"
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "$JWT_PRIVATE_SECRET_NAME" --file "$priv" --only-show-errors >/dev/null
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "$JWT_PUBLIC_SECRET_NAME" --file "$pub" --only-show-errors >/dev/null
'''
  }
}

// Outputs
output keyVaultName string = keyVault.name
output jwtPrivateSecretName string = jwtPrivateSecretName
output jwtPublicSecretName string = jwtPublicSecretName
