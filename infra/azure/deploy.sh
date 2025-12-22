#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Azure ARM Template Deployment Script for Copilot for Consensus
# This script deploys the entire Copilot for Consensus architecture to Azure
# using Azure Resource Manager templates with managed identity support.

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

Deploy Copilot for Consensus to Azure using ARM templates.

OPTIONS:
    -g, --resource-group    Resource group name (required)
    -l, --location          Azure region (default: eastus)
    -p, --parameters        Path to parameters file (default: azuredeploy.parameters.json)
    -n, --project-name      Project name prefix (default: copilot)
    -e, --environment       Environment (dev/staging/prod, default: dev)
    -t, --image-tag         Container image tag (default: latest)
    -v, --validate-only     Validate template without deploying
    -h, --help              Display this help message

EXAMPLES:
    # Deploy with default parameters
    $0 -g my-resource-group

    # Deploy with custom parameters file
    $0 -g my-resource-group -p custom-parameters.json

    # Validate template only
    $0 -g my-resource-group -v

EOF
}

# Default values
RESOURCE_GROUP=""
LOCATION="eastus"
PARAMETERS_FILE="azuredeploy.parameters.json"
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

# Check if parameters file exists
if [ ! -f "$SCRIPT_DIR/$PARAMETERS_FILE" ]; then
    print_error "Parameters file not found: $SCRIPT_DIR/$PARAMETERS_FILE"
    exit 1
fi

# Main deployment
main() {
    check_prerequisites
    
    print_info "Deployment Configuration:"
    print_info "  Resource Group: $RESOURCE_GROUP"
    print_info "  Location: $LOCATION"
    print_info "  Project Name: $PROJECT_NAME"
    print_info "  Environment: $ENVIRONMENT"
    print_info "  Image Tag: $IMAGE_TAG"
    print_info "  Parameters File: $PARAMETERS_FILE"
    
    # Create resource group if it doesn't exist
    print_info "Checking if resource group exists..."
    if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_info "Creating resource group: $RESOURCE_GROUP"
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    else
        print_info "Resource group already exists: $RESOURCE_GROUP"
    fi
    
    # Validate template
    print_info "Validating ARM template..."
    if ! az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/azuredeploy.json" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters projectName="$PROJECT_NAME" environment="$ENVIRONMENT" containerImageTag="$IMAGE_TAG" location="$LOCATION"; then
        print_error "Template validation failed."
        exit 1
    fi
    print_info "Template validation passed."
    
    if [ "$VALIDATE_ONLY" = true ]; then
        print_info "Validation complete. Skipping deployment (--validate-only specified)."
        exit 0
    fi
    
    # Deploy template
    print_info "Starting deployment..."
    DEPLOYMENT_NAME="${PROJECT_NAME}-deployment-$(date +%Y%m%d-%H%M%S)"
    
    # Deploy template
    # NOTE: Parameters specified on the command line override those in the parameters file.
    # This allows script arguments (projectName, environment, etc.) to take precedence.
    if az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/azuredeploy.json" \
        --parameters "@$SCRIPT_DIR/$PARAMETERS_FILE" \
        --parameters projectName="$PROJECT_NAME" environment="$ENVIRONMENT" containerImageTag="$IMAGE_TAG" location="$LOCATION"; then
        
        print_info "Deployment completed successfully!"
        
        # Show deployment outputs
        print_info "Retrieving deployment outputs..."
        az deployment group show \
            --name "$DEPLOYMENT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query properties.outputs
        
        print_info ""
        print_info "Next steps:"
        print_info "1. Verify the deployment in Azure Portal"
        print_info "2. Configure secrets in Azure Key Vault"
        print_info "3. Test the services using the gateway URL from outputs"
    else
        print_error "Deployment failed. Check the error messages above."
        exit 1
    fi
}

# Run main function
main
