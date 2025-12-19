<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Secrets Directory

This directory is mounted into service containers at `/run/secrets` for local development.

Use this folder to store test secrets and credentials:
- Authentication provider tokens (OIDC client IDs and secrets)
- API keys (e.g., Azure OpenAI)
- Database credentials
- Other sensitive configuration

Examples for testing OIDC:
```bash
echo "your-github-client-id" > secrets/github_oauth_client_id
echo "your-github-client-secret" > secrets/github_oauth_client_secret
```

Examples for infrastructure:
```bash
echo "guest" > secrets/rabbitmq_user
echo "guest" > secrets/rabbitmq_pass
```

Secrets in this directory are NOT committed to version control (.gitignore entry).
