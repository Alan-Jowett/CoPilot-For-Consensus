# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

<#
.SYNOPSIS
    Deploys Copilot for Consensus to Azure using the Bicep template.

.DESCRIPTION
    This script deploys the entire Copilot for Consensus architecture to Azure
    using the main Bicep template with managed identity support.

.PARAMETER ResourceGroup
    The name of the Azure resource group to deploy to (required).

.PARAMETER Location
    The Azure region to deploy to (default: eastus).

.PARAMETER ParametersFile
    Path to the parameters file (default: parameters.dev.json).

.PARAMETER ProjectName
    Project name prefix for resources (default: copilot).

.PARAMETER Environment
    Environment name: dev, staging, or prod (default: dev).

.PARAMETER ImageTag
    Container image tag to deploy (default: azure).

.PARAMETER ValidateOnly
    Only validate the template without deploying.

.EXAMPLE
    .\deploy.ps1 -ResourceGroup "my-resource-group"

.EXAMPLE
    .\deploy.ps1 -ResourceGroup "my-resource-group" -ParametersFile "custom-parameters.json"

.EXAMPLE
    .\deploy.ps1 -ResourceGroup "my-resource-group" -ValidateOnly
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",

    [Parameter(Mandatory=$false)]
    [string]$ParametersFile = "parameters.dev.json",

    [Parameter(Mandatory=$false)]
    [string]$ProjectName = "copilot",

    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "azure",

    [Parameter(Mandatory=$false)]
    [switch]$ValidateOnly
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Function to write colored output
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

function Invoke-AzCli {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    Write-Info "az $($Args -join ' ')"
    # Capture only stdout (successful output) for JSON parsing
    # stderr is displayed directly to console if warnings/errors occur
    $output = az @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Command failed: az $($Args -join ' ')"
        throw "az CLI command failed"
    }
    return $output
}

# Function to check prerequisites (az CLI + login)
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."

    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Error-Custom "Azure CLI (az) is not installed. Install from https://learn.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    }

    try {
        Invoke-AzCli account show | Out-Null
    }
    catch {
        Write-Error-Custom "Not logged in to Azure. Please run 'az login' or 'Connect-AzAccount' in this session."
        exit 1
    }

    Write-Info "Prerequisites check passed."
}

# Main deployment function
function Start-Deployment {
    # Get script directory
    $ScriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($ScriptDir)) {
        $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrEmpty($ScriptDir)) {
        $ScriptDir = Get-Location
    }

    # Check prerequisites
    Test-Prerequisites

    Write-Info "Deployment Configuration:"
    Write-Info "  Resource Group: $ResourceGroup"
    Write-Info "  Location: $Location"
    Write-Info "  Project Name: $ProjectName"
    Write-Info "  Environment: $Environment"
    Write-Info "  Image Tag: $ImageTag"
    Write-Info "  Parameters File: $ParametersFile"

    # Check if parameters file exists
    $ParametersPath = Join-Path $ScriptDir $ParametersFile
    if (-not (Test-Path $ParametersPath)) {
        Write-Error-Custom "Parameters file not found: $ParametersPath"
        exit 1
    }

    # Create resource group if it doesn't exist
    Write-Info "Checking if resource group exists..."
    $rgCheck = az group show --name $ResourceGroup 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Creating resource group: $ResourceGroup"
        Invoke-AzCli group create --name $ResourceGroup --location $Location | Out-Null
    }
    else {
        Write-Info "Resource group already exists: $ResourceGroup"
    }

    # Prepare template and parameters
    $TemplatePath = Join-Path $ScriptDir "main.bicep"

    # Read GitHub OIDC secrets if they exist
    $SecretsDir = Join-Path $ScriptDir "../../secrets"
    $githubClientId = ""
    $githubClientSecret = ""

    $clientIdFile = Join-Path $SecretsDir "github_oauth_client_id"
    $clientSecretFile = Join-Path $SecretsDir "github_oauth_client_secret"

    if (Test-Path $clientIdFile) {
        $githubClientId = (Get-Content $clientIdFile -Raw).Trim()
        Write-Info "Found GitHub OAuth client ID secret"
    }

    if (Test-Path $clientSecretFile) {
        $githubClientSecret = (Get-Content $clientSecretFile -Raw).Trim()
        Write-Info "Found GitHub OAuth client secret"
    }

    # Validate template
    Write-Info "Validating Bicep template..."
    Invoke-AzCli deployment group validate `
        --resource-group $ResourceGroup `
        --template-file $TemplatePath `
        --parameters "@$ParametersPath" projectName=$ProjectName environment=$Environment containerImageTag=$ImageTag location=$Location githubOAuthClientId="$githubClientId" githubOAuthClientSecret="$githubClientSecret" | Out-Null

    Write-Info "Template validation passed."

    if ($ValidateOnly) {
        Write-Info "Validation complete. Skipping deployment (-ValidateOnly specified)."
        return
    }

    # Deploy template
    Write-Info "Starting deployment..."
    $DeploymentName = "$ProjectName-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

    Invoke-AzCli deployment group create `
        --name $DeploymentName `
        --resource-group $ResourceGroup `
        --template-file $TemplatePath `
        --parameters "@$ParametersPath" projectName=$ProjectName environment=$Environment containerImageTag=$ImageTag location=$Location githubOAuthClientId="$githubClientId" githubOAuthClientSecret="$githubClientSecret" | Out-Null

    Write-Info "Deployment completed successfully!"

    # Show deployment outputs
    Write-Info "Retrieving deployment outputs..."
    $outputs = Invoke-AzCli deployment group show `
        --name $DeploymentName `
        --resource-group $ResourceGroup `
        --query properties.outputs

    # Parse outputs
    $outputsJson = $outputs | ConvertFrom-Json
    $githubOAuthRedirectUri = $outputsJson.githubOAuthRedirectUri.value

    # Pretty-print outputs for readability
    $outputs | ConvertFrom-Json | ConvertTo-Json -Depth 10

    # Post-deployment: Update auth app with GitHub OAuth redirect URI
    if ($githubOAuthRedirectUri) {
        Write-Info "Updating auth service with GitHub OAuth redirect URI: $githubOAuthRedirectUri"

        # Get the auth app resource
        $authAppName = "$ProjectName-auth-$Environment"

        # Update the AUTH_GITHUB_REDIRECT_URI environment variable via az containerapp update
        try {
            Invoke-AzCli containerapp update `
                --name $authAppName `
                --resource-group $ResourceGroup `
                --set-env-vars "AUTH_GITHUB_REDIRECT_URI=$githubOAuthRedirectUri" | Out-Null

            Write-Info "Successfully updated auth service with GitHub OAuth redirect URI"
        }
        catch {
            Write-Warning-Custom "Failed to update auth service with GitHub OAuth redirect URI. This may need to be done manually."
            Write-Warning-Custom "Command: az containerapp update --name $authAppName --resource-group $ResourceGroup --set-env-vars AUTH_GITHUB_REDIRECT_URI=$githubOAuthRedirectUri"
        }
    }

    Write-Info ""
    Write-Info "Deployment completed successfully!"
    Write-Info ""
    Write-Info "Next steps:"
    Write-Info "1. Verify the deployment in Azure Portal"
    Write-Info "2. Check Azure Key Vault for secrets: github-oauth-client-id, github-oauth-client-secret"
    Write-Info "3. Test the services using the gateway URL from outputs"
}

# Run deployment
Start-Deployment
