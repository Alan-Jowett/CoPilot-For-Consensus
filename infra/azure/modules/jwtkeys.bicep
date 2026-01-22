// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Create RSA cryptographic key in Key Vault for JWT signing via deployment script'

@description('Location for resources')
param location string

@description('Azure Key Vault name to store JWT key')
param keyVaultName string

@description('User-assigned managed identity resource ID used to create keys')
param scriptIdentityId string

@description('Force tag to rerun the key creation script each deployment')
param forceUpdateTag string

@description('Name of the RSA key to create in Key Vault for JWT signing')
param jwtKeyName string = 'jwt-auth-key'

@description('RSA key size in bits')
param jwtKeySize int = 3072

@description('Maximum retries when creating JWT key (to allow RBAC propagation)')
param jwtKeysMaxRetries int = 30

@description('Delay in seconds between retries when creating JWT key')
param jwtKeysRetryDelaySeconds int = 30

param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Deployment script creates an RSA cryptographic key in Key Vault for JWT signing
resource jwtKeyScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'create-jwt-key'
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
        name: 'JWT_KEY_NAME'
        value: jwtKeyName
      }
      {
        name: 'JWT_KEY_SIZE'
        value: string(jwtKeySize)
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
function Handle-KeyError {
  param(
    [string]$errorMessage,
    [int]$attempt,
    [int]$maxRetries,
    [int]$retryDelay
  )

  # Use case-insensitive matching because Azure error casing can vary
  if ($errorMessage -imatch "(\bForbidden\b|\bParentResourceNotFound\b|\bis not authorized to perform action\b|\bdoes not have keys/create permission\b)") {
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
$jwtKeyName = $env:JWT_KEY_NAME
$jwtKeySize = [int]$env:JWT_KEY_SIZE
$maxRetries = [int]$env:JWT_MAX_RETRIES
$retryDelay = [int]$env:JWT_RETRY_DELAY_SECONDS

Write-Host "Creating JWT RSA key in Key Vault (with retry for RBAC propagation)..."
Write-Host "  Key Vault: $keyVaultName"
Write-Host "  Key Name: $jwtKeyName"
Write-Host "  Key Size: $jwtKeySize bits"

$keyCreated = $false

for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
  try {
    # Check if key already exists
    $existingKey = Get-AzKeyVaultKey -VaultName $keyVaultName -Name $jwtKeyName -ErrorAction SilentlyContinue
    if ($existingKey) {
      Write-Host "JWT RSA key already exists: $($existingKey.Id)"
      $keyCreated = $true
      break
    }

    # Create new RSA key in Key Vault
    $addParams = @{
      VaultName = $keyVaultName
      Name = $jwtKeyName
      KeyType = 'RSA'
      ErrorAction = 'Stop'
    }

    $addCmd = Get-Command Add-AzKeyVaultKey -ErrorAction Stop
    if ($addCmd.Parameters.ContainsKey('Destination')) {
      # Some Az.KeyVault versions require Destination; default to software-protected keys.
      $addParams['Destination'] = 'Software'
    }
    if ($addCmd.Parameters.ContainsKey('KeySize')) {
      $addParams['KeySize'] = $jwtKeySize
    }
    elseif ($addCmd.Parameters.ContainsKey('Size')) {
      $addParams['Size'] = $jwtKeySize
    }
    else {
      throw "Add-AzKeyVaultKey does not support a key size parameter (expected -KeySize or -Size)."
    }

    $key = Add-AzKeyVaultKey @addParams
    Write-Host "JWT RSA key created successfully: $($key.Id)"
    Write-Host "  Key Version: $($key.Version)"
    $keyCreated = $true
    break
  }
  catch {
    $errorMessage = $_.Exception.Message
    if (Handle-KeyError -errorMessage $errorMessage -attempt $attempt -maxRetries $maxRetries -retryDelay $retryDelay) { continue }
  }
}

if (-not $keyCreated) {
  throw "Failed to create JWT RSA key in Key Vault after $maxRetries attempts"
}

# Output the key information for use by other deployments
$DeploymentScriptOutputs = @{}
$DeploymentScriptOutputs['jwtKeyName'] = $jwtKeyName
$DeploymentScriptOutputs['keyVaultName'] = $keyVaultName
'''
  }
}

// Outputs
output keyVaultName string = keyVault.name
output jwtKeyName string = jwtKeyName
output jwtKeyUri string = '${keyVault.properties.vaultUri}keys/${jwtKeyName}'
