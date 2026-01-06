#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Azure Bicep Deployment Script for Environment Infrastructure
# This script deploys environment-specific resources (ACA, storage, data, etc.)
# Requires Core infrastructure to be deployed first (deploy.core.sh)

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

Deploy Environment infrastructure (ACA, storage, data, observability) to Azure.
PREREQUISITE: Core infrastructure must be deployed first (deploy.core.sh).

OPTIONS:
    -g, --resource-group    Environment resource group name (required)
    -l, --location          Azure region (default: westus)
    -p, --parameters        Path to parameters file (default: parameters.<env>.json)
    -n, --project-name      Project name prefix (default: copilot)
    -e, --environment       Environment (dev/staging/prod, default: dev)
    -t, --image-tag         Container image tag (default: latest)
    -v, --validate-only     Validate template without deploying
    -h, --help              Display this help message

EXAMPLES:
    # Deploy environment for dev
    $0 -g rg-env-dev -e dev

    # Deploy environment with custom parameters
    $0 -g rg-env-staging -p parameters.staging.json -e staging

    # Validate template only
    $0 -g rg-env-dev -e dev -v

IMPORTANT:
    Before deploying, ensure your parameters file contains the Core outputs:
    - azureOpenAIEndpoint
    - azureOpenAIGptDeploymentName
    - azureOpenAIEmbeddingDeploymentName
    - coreKeyVaultResourceId
    - coreKeyVaultName
    - coreKvSecretUriAoaiKey

EOF
}

# Default values
RESOURCE_GROUP=""
LOCATION="westus"
PARAMETERS_FILE=""
PROJECT_NAME="copilot"
ENVIRONMENT="dev"
IMAGE_TAG="latest"
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
        -n|--project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--image-tag)
            IMAGE_TAG="$2"
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

# Validate required parameters
if [ -z "$RESOURCE_GROUP" ]; then
    print_error "Resource group name is required."
    usage
    exit 1
fi

# Auto-detect parameters file if not specified
if [ -z "$PARAMETERS_FILE" ]; then
    PARAMETERS_FILE="parameters.${ENVIRONMENT}.json"
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
    print_warning "ENVIRONMENT INFRASTRUCTURE DEPLOYMENT"
    print_warning "==================================================================="
    print_warning "This deploys ACA, storage, data, and observability resources."
    print_warning "Azure OpenAI is NOT included (it's in the Core RG)."
    print_warning "This environment can be safely deleted and redeployed."
    print_warning "==================================================================="
    print_info ""
    print_info "Deployment Configuration:"
    print_info "  Resource Group: $RESOURCE_GROUP (Env - disposable)"
    print_info "  Location: $LOCATION"
    print_info "  Project Name: $PROJECT_NAME"
    print_info "  Environment: $ENVIRONMENT"
    print_info "  Image Tag: $IMAGE_TAG"
    print_info "  Parameters File: $PARAMETERS_FILE"

    # Create resource group if it doesn't exist
    print_info "Checking if environment resource group exists..."
    if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_info "Creating environment resource group: $RESOURCE_GROUP"
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags scope=env environment="$ENVIRONMENT"
    else
        print_info "Environment resource group already exists: $RESOURCE_GROUP"
    fi

    # Validate template
    print_info "Validating Environment Bicep template..."
    if ! az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/main.bicep" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters projectName="$PROJECT_NAME" environment="$ENVIRONMENT" containerImageTag="$IMAGE_TAG" location="$LOCATION"; then
        print_error "Template validation failed."
        print_error "Ensure your parameters file contains all required Core outputs (see deploy.core.sh)."
        exit 1
    fi
    print_info "Template validation passed."

    if [ "$VALIDATE_ONLY" = true ]; then
        print_info "Validation complete. Skipping deployment (--validate-only specified)."
        exit 0
    fi

    # Deploy template
    print_info "Starting environment deployment..."
    DEPLOYMENT_NAME="${PROJECT_NAME}-env-deployment-$(date +%Y%m%d-%H%M%S)"

    if az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/main.bicep" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters projectName="$PROJECT_NAME" environment="$ENVIRONMENT" containerImageTag="$IMAGE_TAG" location="$LOCATION"; then

        print_info "Environment deployment completed successfully!"

        # Show deployment outputs
        print_info "Retrieving deployment outputs..."
        az deployment group show \
            --name "$DEPLOYMENT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query properties.outputs

        print_info ""
        print_info "Next steps:"
        print_info "1. Verify the deployment in Azure Portal"
        print_info "2. Configure additional secrets in Env Key Vault if needed"
        print_info "3. Test the services using the gateway URL from outputs"
        print_info ""
        print_warning "To delete this environment: Use delete.env.sh (NOT 'az group delete' directly)"
    else
        print_error "Environment deployment failed. Check the error messages above."
        exit 1
    fi
}

# Run main function
main
