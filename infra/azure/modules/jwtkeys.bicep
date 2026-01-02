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

@description('Maximum retries when writing JWT secrets (to allow RBAC propagation)')
param jwtKeysMaxRetries int = 30

@description('Delay in seconds between retries when writing JWT secrets')
param jwtKeysRetryDelaySeconds int = 30

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
      {
        name: 'JWT_MAX_RETRIES'
        value: string(jwtKeysMaxRetries)
      }
      {
        name: 'JWT_RETRY_DELAY_SECONDS'
        value: string(jwtKeysRetryDelaySeconds)
      }
    ]
    scriptContent: '''
# Helper function to format base64 string for PEM (64 chars per line)
function Format-Base64ForPem {
    param([string]$base64String)
    $lines = @()
    for ($i = 0; $i -lt $base64String.Length; $i += 64) {
        $lines += $base64String.Substring($i, [Math]::Min(64, $base64String.Length - $i))
    }
    return $lines -join "`n"
}

function Handle-SecretError {
  param(
    [string]$errorMessage,
    [int]$attempt,
    [int]$maxRetries,
    [int]$retryDelay
  )

  # Use case-insensitive matching because Azure error casing can vary
  if ($errorMessage -imatch "(\bForbidden\b|\bParentResourceNotFound\b|\bis not authorized to perform action\b|\bdoes not have secrets/set permission\b)") {
    if ($attempt -lt $maxRetries) {
      Write-Warning "Permission error on attempt $attempt of $maxRetries. RBAC may still be propagating. Waiting $retryDelay seconds before retry..."
      Write-Warning "Error: $errorMessage"
      Start-Sleep -Seconds $retryDelay
      return $true
    }
    else {
      Write-Error "Failed after $maxRetries attempts. RBAC permissions not propagated. Error: $errorMessage"
      throw
    }
  }
  else {
    Write-Error "Unexpected error: $errorMessage"
    throw
  }
}

$VerbosePreference = 'Continue'
# Give RBAC assignments time to propagate before first write attempt.
# NOTE: This initial delay is in addition to the retry logic below.
# With the current defaults (maxRetries = 30, retryDelay = 30s), the worst-case
# total wait time before failing is:
#   initialDelaySeconds + (maxRetries - 1) * retryDelay
#   = 90 + (30 - 1) * 30 = 960 seconds (~16 minutes) with the default 90s initial delay.
# This is intentional to accommodate slow RBAC propagation in some environments.
$initialDelaySeconds = 90
Start-Sleep -Seconds $initialDelaySeconds
$keyVaultName = $env:KEY_VAULT_NAME
$privateSecretName = $env:JWT_PRIVATE_SECRET_NAME
$publicSecretName = $env:JWT_PUBLIC_SECRET_NAME

# Use .NET for RSA key generation (available by default in PowerShell)
$rsa = [System.Security.Cryptography.RSA]::Create(3072)

# Export private key in PEM format with proper 64-character line wrapping
$privateKeyBase64 = [System.Convert]::ToBase64String($rsa.ExportRSAPrivateKey())
$privateKeyFormatted = "-----BEGIN RSA PRIVATE KEY-----`n" + (Format-Base64ForPem -base64String $privateKeyBase64) + "`n-----END RSA PRIVATE KEY-----"

# Export public key in PEM format with proper 64-character line wrapping
$publicKeyBase64 = [System.Convert]::ToBase64String($rsa.ExportSubjectPublicKeyInfo())
$publicKeyFormatted = "-----BEGIN PUBLIC KEY-----`n" + (Format-Base64ForPem -base64String $publicKeyBase64) + "`n-----END PUBLIC KEY-----"

# Store in Key Vault with retry logic for RBAC propagation delays
# Azure RBAC can take up to 5 minutes to propagate after role assignment
$maxRetries = [int]$env:JWT_MAX_RETRIES
$retryDelay = [int]$env:JWT_RETRY_DELAY_SECONDS  # 30 seconds between retries => 29 delays (~14.5 minutes retry delay with 30 retries; see total worst-case wait-time calculation above)
$privateStored = $false
$publicStored = $false

Write-Host "Storing JWT keys in Key Vault (with retry for RBAC propagation)..."

for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
  try {
    if (-not $privateStored) {
      Set-AzKeyVaultSecret -VaultName $keyVaultName -Name $privateSecretName -SecretValue (ConvertTo-SecureString -String $privateKeyFormatted -AsPlainText -Force) -ErrorAction Stop | Out-Null
      $privateStored = $true
    }
  }
  catch {
    $errorMessage = $_.Exception.Message
    if (Handle-SecretError -errorMessage $errorMessage -attempt $attempt -maxRetries $maxRetries -retryDelay $retryDelay) { continue }
  }

  try {
    if (-not $publicStored) {
      Set-AzKeyVaultSecret -VaultName $keyVaultName -Name $publicSecretName -SecretValue (ConvertTo-SecureString -String $publicKeyFormatted -AsPlainText -Force) -ErrorAction Stop | Out-Null
      $publicStored = $true
    }
  }
  catch {
    $errorMessage = $_.Exception.Message
    if (Handle-SecretError -errorMessage $errorMessage -attempt $attempt -maxRetries $maxRetries -retryDelay $retryDelay) { continue }
  }

  if ($privateStored -and $publicStored) {
    Write-Host "JWT keys generated and stored successfully (attempt $attempt)"
    break
  }
}

if (-not ($privateStored -and $publicStored)) {
  throw "Failed to store both JWT secrets in Key Vault after $maxRetries attempts. Private stored: $privateStored; Public stored: $publicStored."
}
'''
  }
}

// Outputs
output keyVaultName string = keyVault.name
output jwtPrivateSecretName string = jwtPrivateSecretName
output jwtPublicSecretName string = jwtPublicSecretName
