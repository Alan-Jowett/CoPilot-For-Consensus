#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Safe Environment Resource Group Deletion Script
# This script deletes environment-specific resources without touching Core infrastructure.
# WARNING: This will permanently delete all environment resources!

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Safely delete Environment infrastructure without touching Core resources.
IMPORTANT: This permanently deletes all environment resources!

OPTIONS:
    -g, --resource-group    Environment resource group name (required)
    -y, --yes               Skip confirmation prompt
    -h, --help              Display this help message

EXAMPLES:
    # Delete environment with confirmation
    $0 -g rg-env-dev

    # Delete environment without confirmation
    $0 -g rg-env-staging -y

SAFETY GUARDRAILS:
    - This script will NOT delete resource groups named "rg-core-*" or "*-core-*"
    - The Core RG (Azure OpenAI + Key Vault) is never touched
    - You can redeploy environments at any time without AOAI cooldown

EOF
}

# Default values
RESOURCE_GROUP=""
SKIP_CONFIRMATION=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -y|--yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$RESOURCE_GROUP" ]; then
    print_error "Resource group name is required."
    usage
    exit 1
fi

# Safety check: Prevent deletion of Core resource groups
if [[ "$RESOURCE_GROUP" == *"core"* ]] || [[ "$RESOURCE_GROUP" == "rg-core-"* ]]; then
    print_error "SAFETY GUARDRAIL TRIGGERED!"
    print_error "Refusing to delete resource group: $RESOURCE_GROUP"
    print_error "This appears to be a Core resource group (contains Azure OpenAI)."
    print_error "Core resources should NEVER be deleted to avoid AOAI capacity cooldown."
    print_error ""
    print_error "If you really need to delete Core infrastructure, use:"
    print_error "  az group delete --name $RESOURCE_GROUP"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    print_error "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Check if resource group exists
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    print_warning "Resource group does not exist: $RESOURCE_GROUP"
    print_info "Nothing to delete."
    exit 0
fi

# Confirmation prompt
if [ "$SKIP_CONFIRMATION" = false ]; then
    print_warning "==================================================================="
    print_warning "WARNING: YOU ARE ABOUT TO DELETE ENVIRONMENT INFRASTRUCTURE"
    print_warning "==================================================================="
    print_warning "Resource Group: $RESOURCE_GROUP"
    print_warning "This will permanently delete:"
    print_warning "  - Container Apps and Container Apps Environment"
    print_warning "  - Cosmos DB accounts"
    print_warning "  - Storage accounts"
    print_warning "  - Service Bus namespaces"
    print_warning "  - Virtual networks"
    print_warning "  - Managed identities"
    print_warning "  - Application Insights"
    print_warning "  - Environment Key Vault (NOT Core Key Vault)"
    print_warning ""
    print_info "The Core RG (Azure OpenAI + Key Vault) will NOT be deleted."
    print_info "You can redeploy this environment at any time."
    print_warning "==================================================================="
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Deletion cancelled."
        exit 0
    fi
fi

# Delete resource group
print_info "Deleting resource group: $RESOURCE_GROUP"
print_warning "This may take several minutes..."

if az group delete --name "$RESOURCE_GROUP" --yes --no-wait; then
    print_info "Deletion initiated successfully (running in background)."
    print_info "To check status: az group show --name $RESOURCE_GROUP"
    print_info ""
    print_info "After deletion completes, you can redeploy using deploy.env.sh"
else
    print_error "Failed to delete resource group."
    exit 1
fi
