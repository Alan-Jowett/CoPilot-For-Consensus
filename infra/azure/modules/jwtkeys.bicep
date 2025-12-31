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
  kind: 'AzurePowerShell'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${scriptIdentityId}': {}
    }
  }
  properties: {
    azPowerShellVersion: '11.0'
    timeout: 'PT15M'
    // Always cleanup to prevent cost accumulation from failed deployments
    // Logs and outputs are retained for 1 day (retentionInterval) for troubleshooting
    cleanupPreference: 'Always'
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
$VerbosePreference = 'Continue'
$keyVaultName = $env:KEY_VAULT_NAME
$privateSecretName = $env:JWT_PRIVATE_SECRET_NAME
$publicSecretName = $env:JWT_PUBLIC_SECRET_NAME

# Use .NET for RSA key generation (always available in PowerShell)
[System.Reflection.Assembly]::LoadWithPartialName('System.Security') | Out-Null
$rsa = [System.Security.Cryptography.RSA]::Create(3072)

# Export private key in PEM format
$privateKeyFormatted = "-----BEGIN RSA PRIVATE KEY-----`n" + [System.Convert]::ToBase64String($rsa.ExportRSAPrivateKey()) + "`n-----END RSA PRIVATE KEY-----"

# Export public key in PEM format
$publicKeyFormatted = "-----BEGIN PUBLIC KEY-----`n" + [System.Convert]::ToBase64String($rsa.ExportSubjectPublicKeyInfo()) + "`n-----END PUBLIC KEY-----"

# Store in Key Vault using Set-AzKeyVaultSecret
Set-AzKeyVaultSecret -VaultName $keyVaultName -Name $privateSecretName -SecretValue (ConvertTo-SecureString -String $privateKeyFormatted -AsPlainText -Force) -ErrorAction Stop | Out-Null
Set-AzKeyVaultSecret -VaultName $keyVaultName -Name $publicSecretName -SecretValue (ConvertTo-SecureString -String $publicKeyFormatted -AsPlainText -Force) -ErrorAction Stop | Out-Null

Write-Host "JWT keys generated and stored successfully"
'''
  }
}

// Outputs
output keyVaultName string = keyVault.name
output jwtPrivateSecretName string = jwtPrivateSecretName
output jwtPublicSecretName string = jwtPublicSecretName
