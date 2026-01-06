#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Azure Bicep Deployment Script for Core Infrastructure (Azure OpenAI + Key Vault)
# This script deploys the long-lived Core infrastructure to Azure.
# WARNING: Do NOT delete the Core resource group - it contains Azure OpenAI which has
# a 24-48 hour capacity cooldown after deletion.

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

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    # Check if logged in to Azure
    if ! az account show &> /dev/null; then
        print_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi

    print_info "Prerequisites check passed."
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Core infrastructure (Azure OpenAI + Key Vault) to Azure.

OPTIONS:
    -g, --resource-group    Core resource group name (default: rg-core-ai)
    -l, --location          Azure region (default: westus)
    -p, --parameters        Path to parameters file (default: parameters.core.dev.json)
    -e, --environment       Environment (dev/staging/prod, default: dev)
    -v, --validate-only     Validate template without deploying
    -h, --help              Display this help message

EXAMPLES:
    # Deploy Core for dev environment
    $0 -g rg-core-ai -e dev

    # Deploy Core for prod with custom parameters
    $0 -g rg-core-ai -p parameters.core.prod.json -e prod

    # Validate template only
    $0 -g rg-core-ai -v

EOF
}

# Default values
RESOURCE_GROUP="rg-core-ai"
LOCATION="westus"
PARAMETERS_FILE=""
ENVIRONMENT="dev"
VALIDATE_ONLY=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -p|--parameters)
            PARAMETERS_FILE="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -v|--validate-only)
            VALIDATE_ONLY=true
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

# Auto-detect parameters file if not specified
if [ -z "$PARAMETERS_FILE" ]; then
    PARAMETERS_FILE="parameters.core.${ENVIRONMENT}.json"
fi

# Check if parameters file exists
if [ ! -f "$SCRIPT_DIR/$PARAMETERS_FILE" ]; then
    print_error "Parameters file not found: $SCRIPT_DIR/$PARAMETERS_FILE"
    exit 1
fi

# Main deployment
main() {
    check_prerequisites

    print_warning "==================================================================="
    print_warning "CORE INFRASTRUCTURE DEPLOYMENT"
    print_warning "==================================================================="
    print_warning "This deploys Azure OpenAI and Key Vault to a LONG-LIVED resource group."
    print_warning "Do NOT delete this resource group after deployment!"
    print_warning "Azure OpenAI has a 24-48 hour capacity cooldown after deletion."
    print_warning "==================================================================="
    print_info ""
    print_info "Deployment Configuration:"
    print_info "  Resource Group: $RESOURCE_GROUP (Core - long-lived)"
    print_info "  Location: $LOCATION"
    print_info "  Environment: $ENVIRONMENT"
    print_info "  Parameters File: $PARAMETERS_FILE"

    # Create resource group if it doesn't exist
    print_info "Checking if Core resource group exists..."
    if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_info "Creating Core resource group: $RESOURCE_GROUP"
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags scope=core environment="$ENVIRONMENT"
    else
        print_info "Core resource group already exists: $RESOURCE_GROUP"
    fi

    # Validate template
    print_info "Validating Core Bicep template..."
    if ! az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/core.bicep" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters location="$LOCATION" environment="$ENVIRONMENT"; then
        print_error "Template validation failed."
        exit 1
    fi
    print_info "Template validation passed."

    if [ "$VALIDATE_ONLY" = true ]; then
        print_info "Validation complete. Skipping deployment (--validate-only specified)."
        exit 0
    fi

    # Deploy template
    print_info "Starting Core deployment..."
    DEPLOYMENT_NAME="core-deployment-$(date +%Y%m%d-%H%M%S)"

    if az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/core.bicep" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters location="$LOCATION" environment="$ENVIRONMENT"; then

        print_info "Core deployment completed successfully!"

        # Show deployment outputs
        print_info "Retrieving Core deployment outputs..."
        az deployment group show \
            --name "$DEPLOYMENT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query properties.outputs

        print_info ""
        print_info "==================================================================="
        print_info "IMPORTANT: Save these outputs for environment deployments!"
        print_info "==================================================================="
        print_info "You will need these values when deploying environments (main.bicep):"
        print_info "  - coreKvResourceId"
        print_info "  - coreKvName"
        print_info "  - aoaiEndpoint"
        print_info "  - aoaiGptDeploymentName"
        print_info "  - aoaiEmbeddingDeploymentName"
        print_info "  - kvSecretUris.aoaiKey"
        print_info ""
        print_info "Update your parameters.*.json files with these values."
        print_info "==================================================================="
    else
        print_error "Core deployment failed. Check the error messages above."
        exit 1
    fi
}

# Run main function
main
