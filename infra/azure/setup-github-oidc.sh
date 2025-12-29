#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# GitHub OIDC Trust Setup Script
# One-time setup to enable GitHub Actions to authenticate to Azure without storing secrets
# This script creates an Azure app registration and federated identity credentials

set -e

# Configuration
GITHUB_ORG="Alan-Jowett"
GITHUB_REPO="CoPilot-For-Consensus"
APP_NAME="github-copilot-consensus-oidc"
SUBSCRIPTION_NAME=${1:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== GitHub OIDC Trust Setup for Azure ===${NC}"

# Check prerequisites
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI not installed. Install from https://docs.microsoft.com/cli/azure/install-azure-cli${NC}"
    exit 1
fi

# Ensure user is logged in
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Logging in to Azure...${NC}"
    az login
fi

# Get subscription details
if [ -z "$SUBSCRIPTION_NAME" ]; then
    echo -e "${YELLOW}Available subscriptions:${NC}"
    az account list --query "[].{name: name, id: id}" -o table
    read -p "Enter subscription name or ID: " SUBSCRIPTION_NAME
fi

SUBSCRIPTION_ID=$(az account show --subscription "$SUBSCRIPTION_NAME" --query id -o tsv)
TENANT_ID=$(az account show --subscription "$SUBSCRIPTION_NAME" --query tenantId -o tsv)

echo -e "${GREEN}✓ Using subscription: $SUBSCRIPTION_NAME (ID: $SUBSCRIPTION_ID)${NC}"
echo -e "${GREEN}✓ Tenant ID: $TENANT_ID${NC}"

# Create Azure AD app registration
echo -e "${YELLOW}Creating app registration: $APP_NAME${NC}"
APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
echo -e "${GREEN}✓ App registration created: $APP_ID${NC}"

# Create service principal
echo -e "${YELLOW}Creating service principal...${NC}"
PRINCIPAL_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo -e "${GREEN}✓ Service principal created: $PRINCIPAL_ID${NC}"

# Assign Contributor role to service principal on subscription
echo -e "${YELLOW}Assigning Contributor role on subscription...${NC}"
az role assignment create \
    --role "Contributor" \
    --assignee "$PRINCIPAL_ID" \
    --scope "/subscriptions/$SUBSCRIPTION_ID"
echo -e "${GREEN}✓ Contributor role assigned${NC}"

# Create federated credential for GitHub main branch
echo -e "${YELLOW}Creating federated credential for GitHub (main branch)...${NC}"
cat > /tmp/federated_cred_main.json <<EOF
{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main",
  "description": "GitHub Actions main branch",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF

az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters /tmp/federated_cred_main.json
echo -e "${GREEN}✓ Federated credential created for main branch${NC}"

# Create federated credential for GitHub PR branches
echo -e "${YELLOW}Creating federated credential for GitHub (PR branches)...${NC}"
cat > /tmp/federated_cred_pr.json <<EOF
{
  "name": "github-prs",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request",
  "description": "GitHub Actions pull requests",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF

az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters /tmp/federated_cred_pr.json
echo -e "${GREEN}✓ Federated credential created for PR branches${NC}"

# Output secrets for GitHub Actions
echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Add these secrets to GitHub repository settings (Settings > Secrets and variables > Actions):"
echo ""
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
echo "AZURE_TENANT_ID: $TENANT_ID"
echo "AZURE_CLIENT_ID: $APP_ID"
echo ""
echo "The workflow will use these to authenticate via OIDC (no client secret needed)."
echo ""
echo "Federated credentials created for:"
echo "  1. Main branch: repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main"
echo "  2. PR branches: repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy the secrets above to GitHub"
echo "2. Run the workflow: Push a change to infra/azure/ or trigger manually"
echo "3. Check GitHub Actions tab for validation results"
echo ""

# Cleanup
rm -f /tmp/federated_cred_main.json /tmp/federated_cred_pr.json
