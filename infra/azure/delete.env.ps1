# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Safe Environment Resource Group Deletion Script
# This script deletes environment-specific resources without touching Core infrastructure.
# WARNING: This will permanently delete all environment resources!

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    [switch]$Yes,
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
Usage: .\delete.env.ps1 [OPTIONS]

Safely delete Environment infrastructure without touching Core resources.
IMPORTANT: This permanently deletes all environment resources!

OPTIONS:
    -ResourceGroup      Environment resource group name (required)
    -Yes                Skip confirmation prompt
    -Help               Display this help message

EXAMPLES:
    # Delete environment with confirmation
    .\delete.env.ps1 -ResourceGroup rg-env-dev

    # Delete environment without confirmation
    .\delete.env.ps1 -ResourceGroup rg-env-staging -Yes

SAFETY GUARDRAILS:
    - This script will NOT delete resource groups named "rg-core-*" or "*-core-*"
    - The Core RG (Azure OpenAI + Key Vault) is never touched
    - You can redeploy environments at any time without AOAI cooldown
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# Safety check: Prevent deletion of Core resource groups
if ($ResourceGroup -like "*core*" -or $ResourceGroup -like "rg-core-*") {
    Write-Error "SAFETY GUARDRAIL TRIGGERED!"
    Write-Error "Refusing to delete resource group: $ResourceGroup"
    Write-Error "This appears to be a Core resource group (contains Azure OpenAI)."
    Write-Error "Core resources should NEVER be deleted to avoid AOAI capacity cooldown."
    Write-Error ""
    Write-Error "If you really need to delete Core infrastructure, use:"
    Write-Error "  az group delete --name $ResourceGroup"
    exit 1
}

# Check if logged in
try {
    az account show | Out-Null
} catch {
    Write-Error "Not logged in to Azure. Please run 'az login' first."
    exit 1
}

# Check if resource group exists
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Warning "Resource group does not exist: $ResourceGroup"
    Write-Info "Nothing to delete."
    exit 0
}

# Confirmation prompt
if (-not $Yes) {
    Write-Warning "==================================================================="
    Write-Warning "WARNING: YOU ARE ABOUT TO DELETE ENVIRONMENT INFRASTRUCTURE"
    Write-Warning "==================================================================="
    Write-Warning "Resource Group: $ResourceGroup"
    Write-Warning "This will permanently delete:"
    Write-Warning "  - Container Apps and Container Apps Environment"
    Write-Warning "  - Cosmos DB accounts"
    Write-Warning "  - Storage accounts"
    Write-Warning "  - Service Bus namespaces"
    Write-Warning "  - Virtual networks"
    Write-Warning "  - Managed identities"
    Write-Warning "  - Application Insights"
    Write-Warning "  - Environment Key Vault (NOT Core Key Vault)"
    Write-Warning ""
    Write-Info "The Core RG (Azure OpenAI + Key Vault) will NOT be deleted."
    Write-Info "You can redeploy this environment at any time."
    Write-Warning "==================================================================="
    $confirmation = Read-Host "Are you sure you want to continue? (yes/no)"
    if ($confirmation -ne "yes") {
        Write-Info "Deletion cancelled."
        exit 0
    }
}

# Delete resource group
Write-Info "Deleting resource group: $ResourceGroup"
Write-Warning "This may take several minutes..."

$deleteResult = az group delete --name $ResourceGroup --yes --no-wait 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Info "Deletion initiated successfully (running in background)."
    Write-Info "To check status: az group show --name $ResourceGroup"
    Write-Info ""
    Write-Info "After deletion completes, you can redeploy using deploy.env.ps1"
} else {
    Write-Error "Failed to delete resource group."
    Write-Host $deleteResult
    exit 1
}
