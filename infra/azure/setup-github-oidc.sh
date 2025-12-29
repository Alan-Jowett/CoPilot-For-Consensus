#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# GitHub OIDC Trust Setup Script
# One-time setup to enable GitHub Actions to authenticate to Azure without storing secrets
# This script creates an Azure app registration and federated identity credentials

set -e

# Configuration
SUBSCRIPTION_NAME=${1:-""}
# GitHub organization and repository can be provided as optional arguments.
# If not provided, they are inferred from the local git remote URL.
GITHUB_ORG=${2:-$(git remote get-url origin 2>/dev/null | sed -n 's#.*[:/]\\([^/]*\\)/[^/]*\\.git.*#\\1#p')}
GITHUB_REPO=${3:-$(git remote get-url origin 2>/dev/null | sed -n 's#.*/\\([^/]*\\)\\.git.*#\\1#p')}
APP_NAME="github-copilot-consensus-oidc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== GitHub OIDC Trust Setup for Azure ===${NC}"

# Validate that org and repo were detected
if [ -z \"$GITHUB_ORG\" ] || [ -z \"$GITHUB_REPO\" ]; then
    echo -e \"${RED}Error: Could not detect GitHub org/repo from git remote.${NC}\"
    echo -e \"${YELLOW}Please provide them as arguments: $0 [subscription] [org] [repo]${NC}\"
    exit 1
fi

echo -e \"${GREEN}✓ Detected GitHub: $GITHUB_ORG/$GITHUB_REPO${NC}\"

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

# Wait for app registration to propagate (Azure AD requires this)
echo -e "${YELLOW}Waiting for app registration to propagate (this takes ~30 seconds)...${NC}"
sleep 30

# Create service principal with retry logic
echo -e "${YELLOW}Creating service principal...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    PRINCIPAL_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv 2>&1)
    if [ $? -eq 0 ] && [ -n "$PRINCIPAL_ID" ]; then
        echo -e "${GREEN}✓ Service principal created: $PRINCIPAL_ID${NC}"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}  Retry $RETRY_COUNT/$MAX_RETRIES: Waiting for Azure AD propagation...${NC}"
            sleep 15
        else
            echo -e "${RED}Error: Failed to create service principal after $MAX_RETRIES attempts.${NC}"
            echo -e "${RED}This is usually due to Azure AD propagation delays.${NC}"
            echo -e "${YELLOW}Try running this command manually after a few minutes:${NC}"
            echo "  az ad sp create --id $APP_ID"
            exit 1
        fi
    fi
done

# Assign Contributor role to service principal on subscription
echo -e "${YELLOW}Assigning Contributor role on subscription...${NC}"
# Wait a moment for service principal to be ready
sleep 10
MAX_RETRIES=5
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    az role assignment create \
        --role "Contributor" \
        --assignee "$PRINCIPAL_ID" \
        --scope "/subscriptions/$SUBSCRIPTION_ID" 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Contributor role assigned${NC}"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}  Retry $RETRY_COUNT/$MAX_RETRIES: Waiting for service principal propagation...${NC}"
            sleep 10
        else
            echo -e "${RED}Error: Failed to assign role after $MAX_RETRIES attempts.${NC}"
            echo -e "${YELLOW}Try running this command manually:${NC}"
            echo "  az role assignment create --role Contributor --assignee $PRINCIPAL_ID --scope /subscriptions/$SUBSCRIPTION_ID"
            exit 1
        fi
    fi
done

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
