# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Azure Bicep Deployment Script for Environment Infrastructure
# This script deploys environment-specific resources (ACA, storage, data, etc.)
# Requires Core infrastructure to be deployed first (deploy.core.ps1)

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    [string]$Location = "westus",
    [string]$ParametersFile = "",
    [string]$ProjectName = "copilot",
    [string]$Environment = "dev",
    [string]$ImageTag = "latest",
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
Usage: .\deploy.env.ps1 [OPTIONS]

Deploy Environment infrastructure (ACA, storage, data, observability) to Azure.
PREREQUISITE: Core infrastructure must be deployed first (deploy.core.ps1).

OPTIONS:
    -ResourceGroup      Environment resource group name (required)
    -Location           Azure region (default: westus)
    -ParametersFile     Path to parameters file (default: parameters.<env>.json)
    -ProjectName        Project name prefix (default: copilot)
    -Environment        Environment (dev/staging/prod, default: dev)
    -ImageTag           Container image tag (default: latest)
    -ValidateOnly       Validate template without deploying
    -Help               Display this help message

EXAMPLES:
    # Deploy environment for dev
    .\deploy.env.ps1 -ResourceGroup rg-env-dev -Environment dev

    # Deploy environment with custom parameters
    .\deploy.env.ps1 -ResourceGroup rg-env-staging -ParametersFile parameters.staging.json -Environment staging

    # Validate template only
    .\deploy.env.ps1 -ResourceGroup rg-env-dev -Environment dev -ValidateOnly

IMPORTANT:
    Before deploying, ensure your parameters file contains the Core outputs:
    - azureOpenAIEndpoint
    - azureOpenAIGptDeploymentName
    - azureOpenAIEmbeddingDeploymentName
    - coreKeyVaultResourceId
    - coreKeyVaultName
    - coreKvSecretUriAoaiKey
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# Auto-detect parameters file if not specified
if ([string]::IsNullOrEmpty($ParametersFile)) {
    $ParametersFile = "parameters.$Environment.json"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ParametersPath = Join-Path $ScriptDir $ParametersFile

# Check if parameters file exists
if (-not (Test-Path $ParametersPath)) {
    Write-Error "Parameters file not found: $ParametersPath"
    exit 1
}

# Validate that Core outputs are populated in parameters file
function Test-CoreParametersPopulated {
    param([string]$ParametersPath)
    
    $content = Get-Content -Path $ParametersPath -Raw
    
    # Check for placeholder values that indicate missing Core outputs
    # Be specific to avoid false positives (e.g., "contentVersion" in schema, version hashes in URIs)
    if ($content -match "REPLACE-WITH-CORE-DEPLOYMENT-OUTPUT" -or 
        $content -match "SUBSCRIPTION-ID" -or 
        $content -match "CORE-KV-NAME" -or 
        $content -match '/secrets/[^/]+/VERSION"') {
        Write-Error "================================================"
        Write-Error "DEPLOYMENT BLOCKED: Core parameters not configured!"
        Write-Error "================================================"
        Write-Error "The parameters file contains placeholder values:"
        Write-Error "  $ParametersPath"
        Write-Error ""
        Write-Error "You must first deploy Core infrastructure and update"
        Write-Error "the parameters file with the Core deployment outputs."
        Write-Error ""
        Write-Error "Steps:"
        Write-Error "  1. Deploy Core: .\deploy.core.ps1 -ResourceGroup rg-core-ai -Environment $Environment"
        Write-Error "  2. Note the Core outputs (aoaiEndpoint, coreKvName, etc.)"
        Write-Error "  3. Update $ParametersFile with these values"
        Write-Error "  4. Re-run this script"
        Write-Error "================================================"
        exit 1
    }
}

Test-CoreParametersPopulated -ParametersPath $ParametersPath

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
Write-Warning "ENVIRONMENT INFRASTRUCTURE DEPLOYMENT"
Write-Warning "==================================================================="
Write-Warning "This deploys ACA, storage, data, and observability resources."
Write-Warning "Azure OpenAI is NOT included (it's in the Core RG)."
Write-Warning "This environment can be safely deleted and redeployed."
Write-Warning "==================================================================="
Write-Info ""
Write-Info "Deployment Configuration:"
Write-Info "  Resource Group: $ResourceGroup (Env - disposable)"
Write-Info "  Location: $Location"
Write-Info "  Project Name: $ProjectName"
Write-Info "  Environment: $Environment"
Write-Info "  Image Tag: $ImageTag"
Write-Info "  Parameters File: $ParametersFile"

# Create resource group if it doesn't exist
Write-Info "Checking if environment resource group exists..."
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Info "Creating environment resource group: $ResourceGroup"
    az group create --name $ResourceGroup --location $Location --tags scope=env environment=$Environment
} else {
    Write-Info "Environment resource group already exists: $ResourceGroup"
}

# Validate template
Write-Info "Validating Environment Bicep template..."
$templatePath = Join-Path $ScriptDir "main.bicep"
$validationResult = az deployment group validate `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters "@$ParametersPath" `
    --parameters projectName=$ProjectName environment=$Environment containerImageTag=$ImageTag location=$Location `
    2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error "Template validation failed."
    Write-Error "Ensure your parameters file contains all required Core outputs (see deploy.core.ps1)."
    Write-Host $validationResult
    exit 1
}
Write-Info "Template validation passed."

if ($ValidateOnly) {
    Write-Info "Validation complete. Skipping deployment (-ValidateOnly specified)."
    exit 0
}

# Deploy template
Write-Info "Starting environment deployment..."
$deploymentName = "$ProjectName-env-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

$deployResult = az deployment group create `
    --name $deploymentName `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters "@$ParametersPath" `
    --parameters projectName=$ProjectName environment=$Environment containerImageTag=$ImageTag location=$Location `
    2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Info "Environment deployment completed successfully!"

    # Show deployment outputs
    Write-Info "Retrieving deployment outputs..."
    az deployment group show `
        --name $deploymentName `
        --resource-group $ResourceGroup `
        --query properties.outputs

    Write-Info ""
    Write-Info "Next steps:"
    Write-Info "1. Verify the deployment in Azure Portal"
    Write-Info "2. Configure additional secrets in Env Key Vault if needed"
    Write-Info "3. Test the services using the gateway URL from outputs"
    Write-Info ""
    Write-Warning "To delete this environment: Use delete.env.ps1 (NOT 'az group delete' directly)"
} else {
    Write-Error "Environment deployment failed. Check the error messages above."
    Write-Host $deployResult
    exit 1
}
