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
    Container image tag to deploy (default: latest).

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
    [string]$ImageTag = "latest",

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

# Function to check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."

    # Check if Azure PowerShell module is installed
    if (-not (Get-Module -ListAvailable -Name Az.Resources)) {
        Write-Error-Custom "Azure PowerShell module (Az.Resources) is not installed."
        Write-Host "Please install it with: Install-Module -Name Az -AllowClobber -Scope CurrentUser"
        exit 1
    }

    # Check if logged in to Azure
    try {
        $context = Get-AzContext
        if (-not $context) {
            Write-Error-Custom "Not logged in to Azure. Please run 'Connect-AzAccount' first."
            exit 1
        }
    }
    catch {
        Write-Error-Custom "Not logged in to Azure. Please run 'Connect-AzAccount' first."
        exit 1
    }

    Write-Info "Prerequisites check passed."
}

# Main deployment function
function Start-Deployment {
    # Get script directory
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

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
    $rg = Get-AzResourceGroup -Name $ResourceGroup -ErrorAction SilentlyContinue
    if (-not $rg) {
        Write-Info "Creating resource group: $ResourceGroup"
        New-AzResourceGroup -Name $ResourceGroup -Location $Location | Out-Null
    }
    else {
        Write-Info "Resource group already exists: $ResourceGroup"
    }

    # Prepare template and parameters
    $TemplatePath = Join-Path $ScriptDir "main.bicep"

    # Validate template
    Write-Info "Validating Bicep template..."
    $validationResult = Test-AzResourceGroupDeployment `
        -ResourceGroupName $ResourceGroup `
        -TemplateFile $TemplatePath `
        -TemplateParameterFile $ParametersPath `
        -projectName $ProjectName `
        -environment $Environment `
        -containerImageTag $ImageTag `
        -location $Location

    if ($validationResult) {
        Write-Error-Custom "Template validation failed:"
        $validationResult | Format-List
        exit 1
    }
    Write-Info "Template validation passed."

    if ($ValidateOnly) {
        Write-Info "Validation complete. Skipping deployment (-ValidateOnly specified)."
        return
    }

    # Deploy template
    Write-Info "Starting deployment..."
    $DeploymentName = "$ProjectName-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

    try {
        $deployment = New-AzResourceGroupDeployment `
            -Name $DeploymentName `
            -ResourceGroupName $ResourceGroup `
            -TemplateFile $TemplatePath `
            -TemplateParameterFile $ParametersPath `
            -projectName $ProjectName `
            -environment $Environment `
            -containerImageTag $ImageTag `
            -location $Location `
            -Verbose

        # NOTE: Parameters specified on the command line override those in the parameters file.
        # This allows script arguments (projectName, environment, etc.) to take precedence.

        Write-Info "Deployment completed successfully!"

        # Show deployment outputs
        Write-Info "Deployment outputs:"
        $deployment.Outputs | Format-Table -AutoSize

        Write-Info ""
        Write-Info "Next steps:"
        Write-Info "1. Verify the deployment in Azure Portal"
        Write-Info "2. Configure secrets in Azure Key Vault"
        Write-Info "3. Test the services using the gateway URL from outputs"
    }
    catch {
        Write-Error-Custom "Deployment failed: $_"
        exit 1
    }
}

# Run deployment
Start-Deployment
