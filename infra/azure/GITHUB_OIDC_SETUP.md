<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# GitHub OIDC Setup Guide

This guide explains how to set up GitHub OIDC (OpenID Connect) authentication for Azure, enabling secure CI/CD validation without storing secrets in GitHub.

## Overview

Instead of using a static Azure service principal secret (which is a security risk), GitHub Actions can authenticate to Azure using OIDC tokens. This is:
- ✅ More secure (no long-lived secrets stored in GitHub)
- ✅ Temporary access (tokens expire after job completion)
- ✅ Auditable (each token includes GitHub metadata: repo, branch, workflow)
- ✅ **Scoped permissions** (limited to validation resource group only)

## Security Model

The setup script implements a **secure-by-default** configuration:

- **Contributor role**: Scoped to `copilot-bicep-validation-rg` only (NOT subscription-level)
- **User Access Administrator**: Also scoped to validation resource group
- **PR validations**: Limited blast radius - malicious PRs cannot access resources outside the validation RG
- **Federated credentials**: Created for both main branch and PRs, but with limited permissions

This prevents malicious pull requests from deploying infrastructure or accessing sensitive resources outside the designated validation environment.

## Prerequisites

- **Azure CLI** installed and logged in (`az login`)
- **Contributor** access to your Azure subscription
- **Application Administrator** or **Global Administrator** role in Azure AD (for creating app registrations)
- **Admin** access to the GitHub repository

## Setup Steps

### 1. Run the OIDC Setup Script

```bash
cd infra/azure
chmod +x setup-github-oidc.sh
./setup-github-oidc.sh
```

The script will:
- Prompt you to select a subscription
- Create an Azure AD app registration
- Create a service principal
- Create validation resource group (if it doesn't exist)
- Assign Contributor role **scoped to validation resource group only**
- Assign User Access Administrator role **scoped to validation resource group only**
- Create federated credentials for GitHub (main branch + PR branches)
- Output three values to copy to GitHub

**Note**: The validation resource group (`copilot-bicep-validation-rg`) will be created automatically if it doesn't exist. This ensures that PR validations are isolated from production resources.

### 2. Copy Secrets to GitHub

Go to your repository: **Settings > Secrets and variables > Actions**

Click "New repository secret" and add:

```
Name: AZURE_SUBSCRIPTION_ID
Value: (from script output)

Name: AZURE_TENANT_ID
Value: (from script output)

Name: AZURE_CLIENT_ID
Value: (from script output)
```

**Note:** No `AZURE_CLIENT_SECRET` needed! OIDC handles authentication.

### 3. Verify Setup

Push a change to `infra/azure/` (or trigger workflow manually in Actions tab).

The workflow should:
1. ✅ Build Bicep templates
2. ✅ Lint for best practices
3. ✅ Validate ARM templates (in validation RG)
4. ✅ Run what-if analysis (in validation RG)
5. ✅ Comment results on PR

**Note**: All validation operations are scoped to the `copilot-bicep-validation-rg` resource group. This ensures that PR validations from external contributors cannot affect production resources or access sensitive data.

## Troubleshooting

### Workflow fails with "Credentials cannot be used"

- Verify secrets are spelled correctly in GitHub
- Check federated credential issuers match: `https://token.actions.githubusercontent.com`
- Ensure service principal has Contributor role: `az role assignment list --assignee <CLIENT_ID> --output table`

### "Subscription not found"

- Verify `AZURE_SUBSCRIPTION_ID` is correct: `az account list --query "[].id" -o tsv`
- Confirm subscription is active: `az account show --subscription <SUBSCRIPTION_ID>`

### Script fails to create app registration

- Ensure you're using an account with **Admin** permissions
- Try: `az account set --subscription <SUBSCRIPTION_ID>` before running

## Security Considerations

### Scoped Permissions

The setup script follows the **principle of least privilege**:

- **Validation Only**: Service principal has Contributor access ONLY to `copilot-bicep-validation-rg`
- **No Subscription Access**: Cannot create/modify resources outside the validation RG
- **PR Safety**: Malicious pull requests are contained to the validation environment
- **Production Isolation**: Production resources are not accessible to CI/CD by default

### Production Deployments

For production deployments, you'll need to:

1. **Option A**: Manually run deployments with appropriate credentials
2. **Option B**: Create a separate service principal with broader permissions for main branch only
3. **Option C**: Extend permissions after reviewing and approving infrastructure changes

**Never** grant subscription-level Contributor to PR workflows, as this exposes your infrastructure to malicious code execution before human review.

### Federated Credentials Scope

Federated credentials are created for:
- **Main branch**: `repo:org/repo:ref:refs/heads/main`
- **PR branches**: `repo:org/repo:pull_request`

Both credentials use the same service principal with **scoped permissions** to the validation RG. This allows PR validations while maintaining security boundaries.

## Cleanup (Optional)

If you need to remove the setup:

```bash
# Delete app registration (this removes service principal + federated credentials automatically)
az ad app delete --id <CLIENT_ID>
```

## References

- [GitHub OIDC in Azure](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Azure AD Federated Credentials](https://learn.microsoft.com/azure/active-directory/workload-identities/workload-identity-federation)
- [Azure CLI - AD App](https://learn.microsoft.com/cli/azure/ad/app)
