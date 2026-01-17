# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#+
.SYNOPSIS
Sets OAuth client credentials in the environment Key Vault and restarts the auth Container App.

.DESCRIPTION
This script is intended for post-deployment configuration when using deploy.env.ps1 (which does not
inject OAuth credentials). It writes secrets into the environment Key Vault and optionally updates
redirect URI environment variables on the auth service.

By default, it will try to discover the Key Vault name and redirect URI from the latest successful
Azure resource-group deployment outputs.

.EXAMPLE
# Use local secret files under repoRoot\secrets and restart auth
.\set.oauth.secrets.ps1 -ResourceGroup copilot-app-01 -Environment dev

.EXAMPLE
# Provide creds explicitly and skip restart
.\set.oauth.secrets.ps1 -ResourceGroup copilot-app-01 -Environment dev -GitHubClientId "..." -GitHubClientSecret "..." -RestartAuth:$false

.EXAMPLE
# If discovery fails, provide the Key Vault name directly
.\set.oauth.secrets.ps1 -ResourceGroup copilot-app-01 -Environment dev -KeyVaultName copilotenvkvsk2ssfjiiek
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [string]$Environment = "dev",

    [string]$ProjectName = "copilot",

    [string]$DeploymentName = "",

    [string]$KeyVaultName = "",

    [string]$GitHubClientId = "",

    [string]$GitHubClientSecret = "",

    [string]$MicrosoftClientId = "",

    [string]$MicrosoftClientSecret = "",

    [string]$GoogleClientId = "",

    [string]$GoogleClientSecret = "",

    [string]$SecretsDir = "",

    [string]$CallbackUri = "",

    [switch]$UpdateRedirectUris,

    [switch]$RestartAuth,

    [switch]$DryRun,

    [switch]$Help
)

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Show-Usage {
    Write-Host @"
Usage: .\set.oauth.secrets.ps1 [OPTIONS]

Writes OAuth client credentials into the environment Key Vault, and optionally updates redirect URIs
and restarts the auth Container App.

OPTIONS:
  -ResourceGroup           Environment resource group name (required)
  -Environment             Environment name (default: dev)
  -ProjectName             Project prefix for Container App names (default: copilot)
  -DeploymentName          Deployment name to read outputs from (default: latest successful)
  -KeyVaultName            Override Key Vault name (skip discovery)

  -GitHubClientId          GitHub OAuth client id (default: read from secrets/github_oauth_client_id)
  -GitHubClientSecret      GitHub OAuth client secret (default: read from secrets/github_oauth_client_secret)

  -MicrosoftClientId       Optional Microsoft OAuth client id
  -MicrosoftClientSecret   Optional Microsoft OAuth client secret
  -GoogleClientId          Optional Google OAuth client id
  -GoogleClientSecret      Optional Google OAuth client secret

  -SecretsDir              Directory containing *_oauth_client_* files (default: <repoRoot>\secrets)
    -CallbackUri             Override callback/redirect URI (e.g. https://dev.copilot-for-consensus.com/ui/callback)
  -UpdateRedirectUris      Update GITHUB/MICROSOFT/GOOGLE *_REDIRECT_URI on auth from deployment output
  -RestartAuth             Restart the auth Container App after updates
  -DryRun                  Print actions without calling Azure
  -Help                    Show this help

NOTES:
  - Secrets are stored in Key Vault as: github-oauth-client-id, github-oauth-client-secret, etc.
  - Redirect URIs are env vars on the auth app: GITHUB_REDIRECT_URI, MICROSOFT_REDIRECT_URI, GOOGLE_REDIRECT_URI.
    - If -CallbackUri is provided, it is used as the redirect URI when -UpdateRedirectUris is enabled.
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# Defaults: be safe for post-deploy by enabling these unless explicitly disabled.
if (-not $PSBoundParameters.ContainsKey('UpdateRedirectUris')) { $UpdateRedirectUris = $true }
if (-not $PSBoundParameters.ContainsKey('RestartAuth')) { $RestartAuth = $true }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

if ([string]::IsNullOrWhiteSpace($SecretsDir)) {
    $SecretsDir = Join-Path $RepoRoot "secrets"
}

function Invoke-Az {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$AzArgs
    )

    function Get-RedactedArgs {
        param([string[]]$AzArgs)

        # Redact any secret values passed via --value
        $redacted = @()
        for ($i = 0; $i -lt $AzArgs.Count; $i++) {
            $arg = $AzArgs[$i]
            $redacted += $arg
            if ($arg -eq "--value" -and ($i + 1) -lt $AzArgs.Count) {
                $redacted += "***REDACTED***"
                $i++
            }
        }
        return $redacted
    }

    $safeArgs = Get-RedactedArgs -AzArgs $AzArgs
    $cmd = "az " + ($safeArgs -join " ")
    $joined = ($AzArgs -join " ")
    $isWriteOperation = $joined -match "\bkeyvault\s+secret\s+set\b|\bcontainerapp\s+update\b|\bcontainerapp\s+restart\b"

    if ($DryRun -and $isWriteOperation) {
        Write-Info "[DryRun] $cmd"
        return $null
    }

    if ($DryRun -and (-not $isWriteOperation)) {
        Write-Info "[DryRun-Read] $cmd"
    }

    $output = & az @AzArgs
    if ($LASTEXITCODE -ne 0) {
        $stderr = $null
        try {
            # Best-effort: az usually writes its error to stdout/stderr; capture a short hint.
            $stderr = ($output | Out-String)
        } catch {
            $stderr = $null
        }
        if ($stderr) {
            $stderr = $stderr.Trim()
        }

        if ($stderr) {
            throw "Azure CLI command failed: $cmd`n$stderr"
        }
        throw "Azure CLI command failed: $cmd"
    }
    return $output
}

function Get-LatestSucceededDeploymentName {
    param([string]$ResourceGroup)

    $name = Invoke-Az -AzArgs @(
        "deployment", "group", "list",
        "--resource-group", $ResourceGroup,
        "--query", "[?properties.provisioningState=='Succeeded'] | sort_by(@, &properties.timestamp) | [-1].name",
        "-o", "tsv"
    )

    if ([string]::IsNullOrWhiteSpace($name)) {
        throw "No successful deployments found in resource group '$ResourceGroup'. Specify -DeploymentName or -KeyVaultName."
    }

    return $name.Trim()
}

function Get-DeploymentOutputs {
    param(
        [string]$ResourceGroup,
        [string]$DeploymentName
    )

    $json = Invoke-Az -AzArgs @(
        "deployment", "group", "show",
        "--resource-group", $ResourceGroup,
        "--name", $DeploymentName,
        "--query", "properties.outputs",
        "-o", "json"
    )

    if ([string]::IsNullOrWhiteSpace($json)) {
        return $null
    }

    return $json | ConvertFrom-Json
}

function Get-TextSecretFromFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    $raw = Get-Content -Path $Path -Raw
    if ($null -eq $raw) { return "" }

    # Trim whitespace and trailing newlines.
    return $raw.Trim()
}

function Restart-ContainerApp {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$ResourceGroup
    )

    # NOTE: `az containerapp restart` is not available in all Azure CLI/extension versions.
    # Prefer restarting active revisions.
    $activeRevisions = Invoke-Az -AzArgs @(
        "containerapp", "revision", "list",
        "--name", $Name,
        "--resource-group", $ResourceGroup,
        "--query", "[?properties.active].name",
        "-o", "tsv"
    )

    $revNames = @()
    if (-not [string]::IsNullOrWhiteSpace($activeRevisions)) {
        $revNames = $activeRevisions -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    }

    if ($revNames.Count -eq 0) {
        Write-Warning-Custom "No active revisions found for '$Name'; skipping restart."
        return
    }

    foreach ($rev in $revNames) {
        Write-Info "Restarting revision: $rev"
        Invoke-Az -AzArgs @(
            "containerapp", "revision", "restart",
            "--name", $Name,
            "--resource-group", $ResourceGroup,
            "--revision", $rev,
            "-o", "none"
        ) | Out-Null
    }
}

# Basic AZ CLI sanity check
try {
    if (-not $DryRun) {
        Invoke-Az -AzArgs @("account", "show", "-o", "none") | Out-Null
    }
} catch {
    Write-Error-Custom "Azure CLI not ready. Make sure you're logged in: az login"
    throw
}

$resolvedDeploymentName = $DeploymentName
$outputs = $null

if ([string]::IsNullOrWhiteSpace($resolvedDeploymentName) -and [string]::IsNullOrWhiteSpace($KeyVaultName)) {
    $resolvedDeploymentName = Get-LatestSucceededDeploymentName -ResourceGroup $ResourceGroup
}

if (-not [string]::IsNullOrWhiteSpace($resolvedDeploymentName)) {
    Write-Info "Using deployment: $resolvedDeploymentName"
    $outputs = Get-DeploymentOutputs -ResourceGroup $ResourceGroup -DeploymentName $resolvedDeploymentName
}

if ([string]::IsNullOrWhiteSpace($KeyVaultName)) {
    if ($outputs -and $outputs.keyVaultName -and $outputs.keyVaultName.value) {
        $KeyVaultName = [string]$outputs.keyVaultName.value
    } else {
        # Fallback: pick the only Key Vault in the RG if present.
        $kv = Invoke-Az -AzArgs @(
            "resource", "list",
            "--resource-group", $ResourceGroup,
            "--resource-type", "Microsoft.KeyVault/vaults",
            "--query", "[].name",
            "-o", "tsv"
        )

        $names = @()
        if (-not [string]::IsNullOrWhiteSpace($kv)) {
            $names = $kv -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        }

        if ($names.Count -eq 1) {
            $KeyVaultName = $names[0]
        } else {
            throw "Unable to discover Key Vault name. Provide -KeyVaultName (found: $($names -join ', '))."
        }
    }
}

Write-Info "Target Key Vault: $KeyVaultName"

# Resolve local secret files (compatible with legacy deploy.ps1)
$githubClientIdFile = Join-Path $SecretsDir "github_oauth_client_id"
$githubClientSecretFile = Join-Path $SecretsDir "github_oauth_client_secret"

if ([string]::IsNullOrWhiteSpace($GitHubClientId)) {
    $GitHubClientId = Get-TextSecretFromFile -Path $githubClientIdFile
}

if ([string]::IsNullOrWhiteSpace($GitHubClientSecret)) {
    $GitHubClientSecret = Get-TextSecretFromFile -Path $githubClientSecretFile
}

if ([string]::IsNullOrWhiteSpace($GitHubClientId) -or [string]::IsNullOrWhiteSpace($GitHubClientSecret)) {
    Write-Warning-Custom "GitHub OAuth client id/secret not provided and/or missing in '$SecretsDir'."
    Write-Warning-Custom "Expected files: $githubClientIdFile and $githubClientSecretFile"
    throw "Missing GitHub OAuth credentials. Provide -GitHubClientId/-GitHubClientSecret or create secret files."
}

Write-Info "Writing OAuth secrets to Key Vault..."

# GitHub
Invoke-Az -AzArgs @(
    "keyvault", "secret", "set",
    "--vault-name", $KeyVaultName,
    "--name", "github-oauth-client-id",
    "--value", $GitHubClientId,
    "-o", "none"
) | Out-Null

Invoke-Az -AzArgs @(
    "keyvault", "secret", "set",
    "--vault-name", $KeyVaultName,
    "--name", "github-oauth-client-secret",
    "--value", $GitHubClientSecret,
    "-o", "none"
) | Out-Null

# Microsoft (optional)
if (-not [string]::IsNullOrWhiteSpace($MicrosoftClientId)) {
    Invoke-Az -AzArgs @(
        "keyvault", "secret", "set",
        "--vault-name", $KeyVaultName,
        "--name", "microsoft-oauth-client-id",
        "--value", $MicrosoftClientId,
        "-o", "none"
    ) | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($MicrosoftClientSecret)) {
    Invoke-Az -AzArgs @(
        "keyvault", "secret", "set",
        "--vault-name", $KeyVaultName,
        "--name", "microsoft-oauth-client-secret",
        "--value", $MicrosoftClientSecret,
        "-o", "none"
    ) | Out-Null
}

# Google (optional)
if (-not [string]::IsNullOrWhiteSpace($GoogleClientId)) {
    Invoke-Az -AzArgs @(
        "keyvault", "secret", "set",
        "--vault-name", $KeyVaultName,
        "--name", "google-oauth-client-id",
        "--value", $GoogleClientId,
        "-o", "none"
    ) | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($GoogleClientSecret)) {
    Invoke-Az -AzArgs @(
        "keyvault", "secret", "set",
        "--vault-name", $KeyVaultName,
        "--name", "google-oauth-client-secret",
        "--value", $GoogleClientSecret,
        "-o", "none"
    ) | Out-Null
}

Write-Info "OAuth secrets updated."

# Optionally update redirect URI env vars on auth (typically: https://<gatewayFqdn>/ui/callback)
if ($UpdateRedirectUris) {
    $redirectUri = ""

    if (-not [string]::IsNullOrWhiteSpace($CallbackUri)) {
        $redirectUri = $CallbackUri.Trim()

        try {
            $parsed = [System.Uri]::new($redirectUri)
            if (-not $parsed.IsAbsoluteUri) {
                throw "CallbackUri must be an absolute URI."
            }
            if ($parsed.Scheme -ne 'https') {
                Write-Warning-Custom "CallbackUri scheme is '$($parsed.Scheme)'; https is strongly recommended."
            }
            if (-not $redirectUri.EndsWith('/ui/callback')) {
                Write-Warning-Custom "CallbackUri does not end with '/ui/callback'. Make sure your UI is configured for this path."
            }
        } catch {
            throw "Invalid -CallbackUri '$redirectUri'. Provide a valid absolute URI (example: https://dev.copilot-for-consensus.com/ui/callback)."
        }
    }

    if ([string]::IsNullOrWhiteSpace($redirectUri) -and $outputs -and $outputs.githubOAuthRedirectUri -and $outputs.githubOAuthRedirectUri.value) {
        $redirectUri = [string]$outputs.githubOAuthRedirectUri.value
    } elseif ([string]::IsNullOrWhiteSpace($redirectUri) -and $outputs -and $outputs.gatewayFqdn -and $outputs.gatewayFqdn.value) {
        $redirectUri = "https://$([string]$outputs.gatewayFqdn.value)/ui/callback"
    }

    if ([string]::IsNullOrWhiteSpace($redirectUri)) {
        Write-Warning-Custom "No redirect URI found in deployment outputs. Skipping redirect URI update."
    } else {
        $authAppName = "$ProjectName-auth-$Environment"
        Write-Info "Updating auth redirect URIs on Container App '$authAppName' to: $redirectUri"

        Invoke-Az -AzArgs @(
            "containerapp", "update",
            "--name", $authAppName,
            "--resource-group", $ResourceGroup,
            "--set-env-vars",
            "GITHUB_REDIRECT_URI=$redirectUri",
            "MICROSOFT_REDIRECT_URI=$redirectUri",
            "GOOGLE_REDIRECT_URI=$redirectUri",
            "-o", "none"
        ) | Out-Null

        Write-Info "Redirect URI env vars updated. Configure your OAuth apps to use this callback URL:" 
        Write-Host "  $redirectUri" -ForegroundColor Cyan
    }
}

if ($RestartAuth) {
    $authAppName = "$ProjectName-auth-$Environment"
    Write-Info "Restarting auth Container App: $authAppName"

    try {
        Restart-ContainerApp -Name $authAppName -ResourceGroup $ResourceGroup
        Write-Info "Auth restarted."
    } catch {
        Write-Warning-Custom "Failed to restart via 'az containerapp revision restart'. Your Azure CLI containerapp extension may be out of date."
        Write-Warning-Custom "Try: az extension add --name containerapp --upgrade"
        throw
    }
}

Write-Info "Done."
