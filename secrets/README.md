<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Secrets Directory

This directory is mounted into service containers at `/run/secrets` for local development.

Use this folder to store test secrets and credentials:
- Authentication provider tokens (OIDC client IDs and secrets)
- API keys (e.g., Azure OpenAI)
- Database credentials
- Other sensitive configuration

## Setting up OAuth Providers

To enable authentication with GitHub, Google, or Microsoft, you need to create OAuth applications and store the credentials here.

### Quick Setup

For each provider you want to enable:

1. **Copy the example files and fill in your credentials:**

   **Linux/macOS (bash):**
   ```bash
   # GitHub
   cp secrets/github_oauth_client_id.example secrets/github_oauth_client_id
   cp secrets/github_oauth_client_secret.example secrets/github_oauth_client_secret
   # Edit these files and replace with your actual credentials
   
   # Google
   cp secrets/google_oauth_client_id.example secrets/google_oauth_client_id
   cp secrets/google_oauth_client_secret.example secrets/google_oauth_client_secret
   # Edit these files and replace with your actual credentials
   
   # Microsoft
   cp secrets/microsoft_oauth_client_id.example secrets/microsoft_oauth_client_id
   cp secrets/microsoft_oauth_client_secret.example secrets/microsoft_oauth_client_secret
   # Edit these files and replace with your actual credentials
   ```

   **Windows (PowerShell):**
   ```powershell
   # GitHub
   Copy-Item secrets/github_oauth_client_id.example secrets/github_oauth_client_id
   Copy-Item secrets/github_oauth_client_secret.example secrets/github_oauth_client_secret
   # Edit these files and replace with your actual credentials
   
   # Google
   Copy-Item secrets/google_oauth_client_id.example secrets/google_oauth_client_id
   Copy-Item secrets/google_oauth_client_secret.example secrets/google_oauth_client_secret
   # Edit these files and replace with your actual credentials
   
   # Microsoft
   Copy-Item secrets/microsoft_oauth_client_id.example secrets/microsoft_oauth_client_id
   Copy-Item secrets/microsoft_oauth_client_secret.example secrets/microsoft_oauth_client_secret
   # Edit these files and replace with your actual credentials
   ```

2. **Restart the auth service:**

   ```bash
   docker compose restart auth
   ```

3. **Verify which providers are configured:**

   ```bash
   curl http://localhost:8080/auth/providers
   ```

### Rotating GitHub OAuth Secrets (Local/Docker Compose)

To rotate GitHub OAuth credentials in your local development environment:

1. **Create new OAuth credentials** in GitHub:
   - Go to your GitHub OAuth App settings
   - Generate a new client secret
   - Note the new client ID and secret

2. **Update the secret files**:

   **Linux/macOS (bash):**
   ```bash
   # Update GitHub OAuth secrets
   echo "NEW_CLIENT_ID" > secrets/github_oauth_client_id
   echo "NEW_CLIENT_SECRET" > secrets/github_oauth_client_secret
   ```

   **Windows (PowerShell):**
   ```powershell
   # Update GitHub OAuth secrets
   "NEW_CLIENT_ID" | Out-File -FilePath secrets/github_oauth_client_id -NoNewline -Encoding ASCII
   "NEW_CLIENT_SECRET" | Out-File -FilePath secrets/github_oauth_client_secret -NoNewline -Encoding ASCII
   ```

3. **Restart the auth and gateway services** to pick up the new secrets:

   ```bash
   docker compose restart auth gateway
   ```

4. **Verify the new credentials work**:

   ```bash
   # Check that GitHub provider is still configured
   curl http://localhost:8080/auth/providers
   
   # Test GitHub OAuth login flow by visiting in browser
   # http://localhost:8080/ui
   ```

5. **Remove old credentials** from GitHub after confirming the new ones work.

#### Alternative: Using Environment Variables

Instead of updating files, you can override secrets using environment variables:

**Linux/macOS (bash):**
```bash
# Set environment variables
export GITHUB_OAUTH_CLIENT_ID="NEW_CLIENT_ID"
export GITHUB_OAUTH_CLIENT_SECRET="NEW_CLIENT_SECRET"

# Restart with environment overrides
docker compose restart auth gateway
```

**Windows (PowerShell):**
```powershell
# Set environment variables
$env:GITHUB_OAUTH_CLIENT_ID = "NEW_CLIENT_ID"
$env:GITHUB_OAUTH_CLIENT_SECRET = "NEW_CLIENT_SECRET"

# Restart with environment overrides
docker compose restart auth gateway
```

**Note**: Environment variable overrides only persist for the current terminal session. For permanent changes, update the secret files.

### Detailed Setup Instructions

Each example file (`.example`) contains detailed instructions on how to create the OAuth application with that provider. For complete setup guides, see:

- [documents/OIDC_LOCAL_TESTING.md](../documents/OIDC_LOCAL_TESTING.md) - Complete OAuth setup guide for all providers
- [auth/README.md](../auth/README.md) - Auth service documentation

## Other Secrets

Examples for infrastructure:
```bash
echo "guest" > secrets/rabbitmq_user
echo "guest" > secrets/rabbitmq_pass
```

## Security Notes

- Secrets in this directory are NOT committed to version control (.gitignore entry)
- Example files (`.example`) ARE committed to help with setup
- For production deployments, use a secure key vault (Azure Key Vault, AWS Secrets Manager, etc.) instead of file-based secrets
