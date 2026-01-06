# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Azure Bicep Deployment Script for Core Infrastructure (Azure OpenAI + Key Vault)
# This script deploys the long-lived Core infrastructure to Azure.
# WARNING: Do NOT delete the Core resource group - it contains Azure OpenAI which has
# a 24-48 hour capacity cooldown after deletion.

param(
    [string]$ResourceGroup = "rg-core-ai",
    [string]$Location = "westus",
    [string]$ParametersFile = "",
    [string]$Environment = "dev",
    [switch]$ValidateOnly,
    [switch]$Help
)

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Show-Usage {
    Write-Host @"
Usage: .\deploy.core.ps1 [OPTIONS]

Deploy Core infrastructure (Azure OpenAI + Key Vault) to Azure.

OPTIONS:
    -ResourceGroup      Core resource group name (default: rg-core-ai)
    -Location           Azure region (default: westus)
    -ParametersFile     Path to parameters file (default: parameters.core.<env>.json)
    -Environment        Environment (dev/staging/prod, default: dev)
    -ValidateOnly       Validate template without deploying
    -Help               Display this help message

EXAMPLES:
    # Deploy Core for dev environment
    .\deploy.core.ps1 -ResourceGroup rg-core-ai -Environment dev

    # Deploy Core for prod with custom parameters
    .\deploy.core.ps1 -ResourceGroup rg-core-ai -ParametersFile parameters.core.prod.json -Environment prod

    # Validate template only
    .\deploy.core.ps1 -ResourceGroup rg-core-ai -ValidateOnly
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# Auto-detect parameters file if not specified
if ([string]::IsNullOrEmpty($ParametersFile)) {
    $ParametersFile = "parameters.core.$Environment.json"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ParametersPath = Join-Path $ScriptDir $ParametersFile

# Check if parameters file exists
if (-not (Test-Path $ParametersPath)) {
    Write-Error "Parameters file not found: $ParametersPath"
    exit 1
}

# Check prerequisites
Write-Info "Checking prerequisites..."
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI is not installed. Please install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Check if logged in
try {
    az account show | Out-Null
} catch {
    Write-Error "Not logged in to Azure. Please run 'az login' first."
    exit 1
}

Write-Warning "==================================================================="
Write-Warning "CORE INFRASTRUCTURE DEPLOYMENT"
Write-Warning "==================================================================="
Write-Warning "This deploys Azure OpenAI and Key Vault to a LONG-LIVED resource group."
Write-Warning "Do NOT delete this resource group after deployment!"
Write-Warning "Azure OpenAI has a 24-48 hour capacity cooldown after deletion."
Write-Warning "==================================================================="
Write-Info ""
Write-Info "Deployment Configuration:"
Write-Info "  Resource Group: $ResourceGroup (Core - long-lived)"
Write-Info "  Location: $Location"
Write-Info "  Environment: $Environment"
Write-Info "  Parameters File: $ParametersFile"

# Create resource group if it doesn't exist
Write-Info "Checking if Core resource group exists..."
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Info "Creating Core resource group: $ResourceGroup"
    az group create --name $ResourceGroup --location $Location --tags scope=core environment=$Environment
} else {
    Write-Info "Core resource group already exists: $ResourceGroup"
}

# Validate template
Write-Info "Validating Core Bicep template..."
$templatePath = Join-Path $ScriptDir "core.bicep"
$validationResult = az deployment group validate `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters "@$ParametersPath" `
    --parameters location=$Location environment=$Environment `
    2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error "Template validation failed."
    Write-Host $validationResult
    exit 1
}
Write-Info "Template validation passed."

if ($ValidateOnly) {
    Write-Info "Validation complete. Skipping deployment (-ValidateOnly specified)."
    exit 0
}

# Deploy template
Write-Info "Starting Core deployment..."
$deploymentName = "core-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

$deployResult = az deployment group create `
    --name $deploymentName `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters "@$ParametersPath" `
    --parameters location=$Location environment=$Environment `
    2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Info "Core deployment completed successfully!"

    # Show deployment outputs
    Write-Info "Retrieving Core deployment outputs..."
    az deployment group show `
        --name $deploymentName `
        --resource-group $ResourceGroup `
        --query properties.outputs

    Write-Info ""
    Write-Warning "==================================================================="
    Write-Warning "IMPORTANT: Save these outputs for environment deployments!"
    Write-Warning "==================================================================="
    Write-Info "You will need these values when deploying environments (main.bicep):"
    Write-Info "  - coreKvResourceId"
    Write-Info "  - coreKvName"
    Write-Info "  - aoaiEndpoint"
    Write-Info "  - aoaiGptDeploymentName"
    Write-Info "  - aoaiEmbeddingDeploymentName"
    Write-Info "  - kvSecretUris.aoaiKey"
    Write-Info ""
    Write-Info "Update your parameters.*.json files with these values."
    Write-Warning "==================================================================="
} else {
    Write-Error "Core deployment failed. Check the error messages above."
    Write-Host $deployResult
    exit 1
}
