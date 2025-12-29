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
# Handle both SSH (git@github.com:org/repo.git) and HTTPS (https://github.com/org/repo.git) formats
GIT_REMOTE=$(git remote get-url origin 2>/dev/null || true)
if [[ "$GIT_REMOTE" == *"github.com"* ]]; then
    # Remove protocol and .git suffix, then extract org/repo
    GIT_PATH="${GIT_REMOTE#*github.com[:/]}"  # Remove leading git@github.com: or https://github.com/
    GIT_PATH="${GIT_PATH%.git}"               # Remove trailing .git
    GITHUB_ORG="${GIT_PATH%/*}"               # Extract org (part before /)
    GITHUB_REPO="${GIT_PATH##*/}"             # Extract repo (part after /)
fi
GITHUB_ORG=${2:-"$GITHUB_ORG"}
GITHUB_REPO=${3:-"$GITHUB_REPO"}
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
    # Count available subscriptions
    SUBSCRIPTION_COUNT=$(az account list --query "length([]) " -o tsv)
    
    if [ "$SUBSCRIPTION_COUNT" -eq 1 ]; then
        # Only one subscription, use it automatically
        SUBSCRIPTION_NAME=$(az account list --query "[0].name" -o tsv)
        echo -e "${GREEN}✓ Only one subscription available, using: $SUBSCRIPTION_NAME${NC}"
    else
        # Multiple subscriptions, show list and prompt
        echo -e "${YELLOW}Available subscriptions:${NC}"
        az account list --query "[].{name: name, id: id}" -o table
        echo ""
        read -p "Enter subscription name or ID: " SUBSCRIPTION_NAME
    fi
fi

SUBSCRIPTION_ID=$(az account show --subscription "$SUBSCRIPTION_NAME" --query id -o tsv | tr -d '\r')
TENANT_ID=$(az account show --subscription "$SUBSCRIPTION_NAME" --query tenantId -o tsv | tr -d '\r')

echo -e "${GREEN}✓ Using subscription: $SUBSCRIPTION_NAME (ID: $SUBSCRIPTION_ID)${NC}"
echo -e "${GREEN}✓ Tenant ID: $TENANT_ID${NC}"

# Create Azure AD app registration
echo -e "${YELLOW}Creating app registration: $APP_NAME${NC}"

# Check if app already exists (in case this script is retried)
EXISTING_APP_ID=$(az ad app list --filter "displayName eq '$APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null | tr -d '\r' || true)
if [ -n "$EXISTING_APP_ID" ] && [ "$EXISTING_APP_ID" != "null" ]; then
    APP_ID="$EXISTING_APP_ID"
    APP_ALREADY_EXISTS=true
    echo -e "${GREEN}✓ App registration already exists: $APP_ID (idempotent)${NC}"
else
    APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv | tr -d '\r')
    APP_ALREADY_EXISTS=false
    echo -e "${GREEN}✓ App registration created: $APP_ID${NC}"
fi

# Wait for app registration to propagate with polling (Azure AD requires this)
# Skip if app already existed (already propagated)
if [ "$APP_ALREADY_EXISTS" = true ]; then
    echo -e "${GREEN}✓ App registration is accessible (already existed)${NC}"
else
    echo -e "${YELLOW}Verifying app registration propagation...${NC}"
    PROPAGATION_TIMEOUT=60
    PROPAGATION_ELAPSED=0
    PROPAGATION_CHECK_INTERVAL=5
    APP_READY=false

    while [ $PROPAGATION_ELAPSED -lt $PROPAGATION_TIMEOUT ]; do
        # Try to retrieve the app to verify it's actually accessible
        if az ad app show --id "$APP_ID" > /dev/null 2>&1; then
            APP_READY=true
            echo -e "${GREEN}✓ App registration is accessible (propagated in ${PROPAGATION_ELAPSED}s)${NC}"
            break
        fi
        
        PROPAGATION_ELAPSED=$((PROPAGATION_ELAPSED + PROPAGATION_CHECK_INTERVAL))
        if [ $PROPAGATION_ELAPSED -lt $PROPAGATION_TIMEOUT ]; then
            echo -e "${YELLOW}  Waiting for Azure AD propagation... (${PROPAGATION_ELAPSED}/${PROPAGATION_TIMEOUT}s)${NC}"
            sleep $PROPAGATION_CHECK_INTERVAL
        fi
    done

    if [ "$APP_READY" = false ]; then
        echo -e "${YELLOW}⚠️  App registration propagation is taking longer than expected.${NC}"
        echo -e "${YELLOW}This can happen during high Azure AD load. You have two options:${NC}"
        echo -e "${YELLOW}1. Wait a moment and retry the script (it will reuse the app registration)${NC}"
        echo -e "${YELLOW}2. Manually create the service principal and federated credentials later${NC}"
        echo -e "${YELLOW}${NC}"
        echo -e "${YELLOW}If you choose to retry, the script will detect the existing app and continue.${NC}"
        exit 1
    fi
fi

# Create service principal with retry logic
echo -e "${YELLOW}Creating service principal...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    SP_OUTPUT=$(az ad sp create --id "$APP_ID" --query id -o tsv 2>&1)
    SP_EXIT_CODE=$?
    
    if [ $SP_EXIT_CODE -eq 0 ] && [ -n "$SP_OUTPUT" ]; then
        PRINCIPAL_ID=$(echo "$SP_OUTPUT" | tr -d '\r')
        echo -e "${GREEN}✓ Service principal created: $PRINCIPAL_ID${NC}"
        break
    else
        # Check if the error is "already exists" (idempotent, OK to ignore)
        if echo "$SP_OUTPUT" | grep -q "already exists"; then
            # If service principal already exists, retrieve its ID
            PRINCIPAL_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv 2>&1 | tr -d '\r')
            if [ -n "$PRINCIPAL_ID" ]; then
                echo -e "${GREEN}✓ Service principal already exists: $PRINCIPAL_ID (idempotent)${NC}"
                break
            fi
        fi
        
        # Check if error is permission-related (fatal, don't retry)
        if echo "$SP_OUTPUT" | grep -qE "(Insufficient|Authorization|permission)"; then
            echo -e "${RED}Error: Insufficient permissions to create service principal.${NC}"
            echo -e "${RED}Details: $SP_OUTPUT${NC}"
            echo -e "${YELLOW}You need 'Application Administrator' or 'Global Administrator' role in Azure AD.${NC}"
            exit 1
        fi
        
        # Otherwise assume it's a propagation issue and retry
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}  Retry $RETRY_COUNT/$MAX_RETRIES: Waiting for Azure AD propagation...${NC}"
            sleep 15
        else
            echo -e "${RED}Error: Failed to create service principal after $MAX_RETRIES attempts.${NC}"
            echo -e "${RED}Details: $SP_OUTPUT${NC}"
            echo -e "${YELLOW}This is usually due to Azure AD propagation delays.${NC}"
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
    ROLE_OUTPUT=$(az role assignment create \
        --role "Contributor" \
        --assignee "$PRINCIPAL_ID" \
        --scope "/subscriptions/$SUBSCRIPTION_ID" 2>&1)
    ROLE_EXIT_CODE=$?
    
    if [ $ROLE_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ Contributor role assigned${NC}"
        break
    else
        # Check if the error is "already exists" (idempotent, OK to ignore)
        if echo "$ROLE_OUTPUT" | grep -q "The role assignment already exists"; then
            echo -e "${GREEN}✓ Contributor role already exists (idempotent)${NC}"
            break
        fi
        
        # Check if error is permission-related (fatal, don't retry)
        if echo "$ROLE_OUTPUT" | grep -qE "(Insufficient|Authorization|permission|AuthorizationFailed)"; then
            echo -e "${RED}Error: Insufficient permissions to assign role.${NC}"
            echo -e "${RED}Details: $ROLE_OUTPUT${NC}"
            echo -e "${YELLOW}You need 'User Access Administrator' or 'Owner' role on the subscription.${NC}"
            exit 1
        fi
        
        # Otherwise assume it's a propagation issue and retry
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}  Retry $RETRY_COUNT/$MAX_RETRIES: Waiting for service principal propagation...${NC}"
            sleep 10
        else
            echo -e "${RED}Error: Failed to assign role after $MAX_RETRIES attempts.${NC}"
            echo -e "${RED}Details: $ROLE_OUTPUT${NC}"
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

FEDERATED_MAIN_OUTPUT=$(az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters /tmp/federated_cred_main.json 2>&1)
FEDERATED_MAIN_EXIT=$?

if [ $FEDERATED_MAIN_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Federated credential created for main branch${NC}"
elif echo "$FEDERATED_MAIN_OUTPUT" | grep -q "already exists"; then
    echo -e "${GREEN}✓ Federated credential already exists for main branch (idempotent)${NC}"
else
    echo -e "${RED}Error creating federated credential for main branch:${NC}"
    echo "$FEDERATED_MAIN_OUTPUT"
    exit 1
fi

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

FEDERATED_PR_OUTPUT=$(az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters /tmp/federated_cred_pr.json 2>&1)
FEDERATED_PR_EXIT=$?

if [ $FEDERATED_PR_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Federated credential created for PR branches${NC}"
elif echo "$FEDERATED_PR_OUTPUT" | grep -q "already exists"; then
    echo -e "${GREEN}✓ Federated credential already exists for PR branches (idempotent)${NC}"
else
    echo -e "${RED}Error creating federated credential for PR branches:${NC}"
    echo "$FEDERATED_PR_OUTPUT"
    exit 1
fi

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
