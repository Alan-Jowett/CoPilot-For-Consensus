# JWT Signing with Azure Key Vault

This document describes how to configure and use Azure Key Vault for JWT signing in the Copilot-for-Consensus authentication service.

## Overview

The authentication service supports two JWT signing modes:

1. **Local Signing** (default): Private keys stored in Key Vault as secrets, signing performed locally
2. **Key Vault Signing** (recommended for production): Private keys never leave Key Vault, signing performed via Key Vault cryptographic operations

## Why Use Key Vault Signing?

### Security Benefits
- **No Key Egress**: Private keys never leave Azure Key Vault
- **HSM-Backed Keys**: Keys can be stored in FIPS 140-2 Level 2 validated HSMs
- **Audit Trail**: All signing operations are logged in Azure Monitor
- **Access Control**: Fine-grained RBAC with `crypto/sign` permission

### Operational Benefits
- **Key Rotation**: Seamless key rotation with multiple active key versions
- **High Availability**: Built-in redundancy and disaster recovery
- **Compliance**: Meets requirements for key management in regulated industries

## Configuration

### Environment Variables

```bash
# JWT Signer Configuration
JWT_SIGNER_TYPE=keyvault  # or "local" (default)
JWT_ALGORITHM=RS256  # RS256, RS384, RS512, ES256, ES384, ES512
JWT_KEY_ID=my-key-2024  # Key identifier for rotation

# Key Vault Configuration (required when JWT_SIGNER_TYPE=keyvault)
JWT_KEY_VAULT_URL=https://my-vault.vault.azure.net/
JWT_KEY_VAULT_KEY_NAME=jwt-signing-key
JWT_KEY_VAULT_KEY_VERSION=  # Optional: uses latest if not specified

# General JWT Configuration
JWT_DEFAULT_EXPIRY=1800  # 30 minutes
AUTH_ISSUER=https://auth.example.com
```

### Local Development

For local development, use local signing mode:

```bash
export JWT_SIGNER_TYPE=local
export JWT_ALGORITHM=RS256
# JWT keys loaded from secrets (jwt_private_key, jwt_public_key)
```

### Production Deployment

For production, use Key Vault signing mode:

```bash
export JWT_SIGNER_TYPE=keyvault
export JWT_KEY_VAULT_URL=https://prod-vault.vault.azure.net/
export JWT_KEY_VAULT_KEY_NAME=jwt-signing-key-prod
export JWT_ALGORITHM=RS256
```

## Infrastructure Setup

### 1. Create Key Vault Key

The auth service needs an RSA or EC key in Azure Key Vault for signing operations.

#### Using Azure CLI

```bash
# Create RSA key (3072-bit recommended)
az keyvault key create \
  --vault-name my-vault \
  --name jwt-signing-key \
  --kty RSA \
  --size 3072 \
  --ops sign verify

# Or create EC key (P-256 recommended for ES256)
az keyvault key create \
  --vault-name my-vault \
  --name jwt-signing-key \
  --kty EC \
  --curve P-256 \
  --ops sign verify
```

#### Using Bicep

```bicep
resource jwtSigningKey 'Microsoft.KeyVault/vaults/keys@2023-07-01' = {
  name: 'jwt-signing-key'
  parent: keyVault
  properties: {
    kty: 'RSA'
    keySize: 3072
    keyOps: [
      'sign'
      'verify'
    ]
  }
}
```

### 2. Grant Permissions

The auth service managed identity needs `crypto/sign` and `keys/get` permissions.

#### Using Azure CLI

```bash
# Get auth service managed identity principal ID
AUTH_PRINCIPAL_ID=$(az containerapp show \
  --name auth \
  --resource-group my-rg \
  --query identity.principalId -o tsv)

# Grant Key Vault Crypto User role (includes sign and get)
az role assignment create \
  --assignee $AUTH_PRINCIPAL_ID \
  --role "Key Vault Crypto User" \
  --scope /subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault-name}
```

#### Using Bicep

```bicep
var keyVaultCryptoUserRoleId = '12338af0-0e69-4776-bea7-57ae8d297424'

resource authIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'auth-identity'
}

resource cryptoUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, authIdentity.id, keyVaultCryptoUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultCryptoUserRoleId)
    principalId: authIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### 3. Update Container Apps Configuration

```bicep
resource authService 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'auth'
  properties: {
    configuration: {
      secrets: [
        // No JWT private key secret needed for Key Vault signing
      ]
    }
    template: {
      containers: [
        {
          name: 'auth'
          env: [
            {
              name: 'JWT_SIGNER_TYPE'
              value: 'keyvault'
            }
            {
              name: 'JWT_KEY_VAULT_URL'
              value: keyVault.properties.vaultUri
            }
            {
              name: 'JWT_KEY_VAULT_KEY_NAME'
              value: 'jwt-signing-key'
            }
            {
              name: 'JWT_ALGORITHM'
              value: 'RS256'
            }
          ]
        }
      ]
    }
  }
}
```

## Key Rotation

### Overview

Key rotation allows you to replace signing keys without invalidating existing tokens. The process involves:

1. Generate a new key version in Key Vault
2. Update the auth service to use the new key version
3. Publish both keys in JWKS for verification
4. Wait for old tokens to expire before removing old key

### Rotation Steps

#### 1. Create New Key Version

```bash
# This creates a new version of the existing key
az keyvault key create \
  --vault-name my-vault \
  --name jwt-signing-key \
  --kty RSA \
  --size 3072 \
  --ops sign verify
```

The new version gets a unique version ID (e.g., `abc123`).

#### 2. Update Auth Service

**Option A: Rolling Update (Recommended)**

Deploy auth service with new key version:

```bash
# Update environment variable
az containerapp update \
  --name auth \
  --resource-group my-rg \
  --set-env-vars "JWT_KEY_VAULT_KEY_VERSION=abc123"
```

New instances use the new key immediately. Old tokens remain valid.

**Option B: Latest Version (Automatic)**

If `JWT_KEY_VAULT_KEY_VERSION` is not set, the service always uses the latest key version. This allows automatic rotation but requires careful coordination, because the auth service maintains an in-memory cache of public keys for the JWKS endpoint.

When running with `JWT_KEY_VAULT_KEY_VERSION` unset, a key rotation in Azure Key Vault will cause the service to start signing with the new key version, but it may continue serving the old public key from JWKS until the service process is restarted or the cache is explicitly refreshed. During this window, newly issued tokens can fail validation by clients that rely on JWKS.

If you use this automatic-latest mode, you MUST either:

- restart all auth service instances immediately after rotating the Key Vault key so they reload the latest public key(s), or
- implement a cache invalidation / reload strategy in the auth service so that JWKS always reflects the active key version(s).

Coordinate this behavior with your clients' JWKS refresh intervals to avoid token validation failures during rotation.

#### 3. Verify JWKS Endpoint

The JWKS endpoint should serve public keys for both versions during the rotation window:

```bash
curl https://auth.example.com/.well-known/jwks.json
```

Expected response:
```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "my-key-2024",
      "use": "sig",
      "alg": "RS256",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

#### 4. Monitor Token Expiry

After the rotation, wait for the JWT default expiry period (default: 30 minutes) before removing the old key version from Key Vault.

### Rollback

If issues occur during rotation, rollback to the previous key version:

```bash
# Get previous version ID
OLD_VERSION=$(az keyvault key list-versions \
  --vault-name my-vault \
  --name jwt-signing-key \
  --query "[1].version" -o tsv)

# Rollback
az containerapp update \
  --name auth \
  --resource-group my-rg \
  --set-env-vars "JWT_KEY_VAULT_KEY_VERSION=$OLD_VERSION"
```

## Algorithm Support

### RSA Algorithms
- **RS256** (SHA-256): Industry standard, widely supported, recommended for most use cases
- **RS384** (SHA-384): Higher security margin, larger signatures
- **RS512** (SHA-512): Maximum security, largest signatures

### EC Algorithms (Recommended for Future)
- **ES256** (P-256 curve): Equivalent security to RSA 3072-bit with smaller keys (~256 bits vs 3072 bits)
- **ES384** (P-384 curve): Equivalent security to RSA 7680-bit (~384 bits vs 7680 bits)
- **ES512** (P-521 curve): Maximum EC security level

**Note**: EC keys provide better performance and smaller tokens while maintaining equivalent security.

## Performance Considerations

### Latency

Key Vault signing adds latency compared to local signing:

- **Local Signing**: ~1-2ms per token
- **Key Vault Signing**: ~50-100ms per token (depends on region and network)

### Mitigation Strategies

1. **Caching**: The service caches public keys to minimize Key Vault calls
2. **Long Token Lifetimes**: Use longer expiry times (e.g., 30 minutes) to reduce token minting frequency
3. **Circuit Breaker**: Prevents cascading failures if Key Vault is unavailable
4. **Retry Logic**: Exponential backoff for transient network errors

### Throughput

For high-throughput scenarios:

- **Key Vault Standard**: ~2000 transactions/10s per vault
- **Key Vault Premium** (HSM-backed): ~2000 transactions/10s per vault per region

If you exceed these limits, consider:
- Multiple vaults across regions
- Regional auth service instances with geo-local vaults
- Increase JWT token lifetime to reduce signing frequency

## Monitoring and Troubleshooting

### Health Check

The auth service exposes a health check endpoint that verifies Key Vault connectivity:

```bash
curl https://auth.example.com/health
```

Expected response when healthy:
```json
{
  "status": "healthy",
  "jwt_signer": "keyvault",
  "key_vault_health": "ok"
}
```

### Azure Monitor Logs

Enable diagnostics for Key Vault to monitor signing operations:

```bash
az monitor diagnostic-settings create \
  --name keyvault-diagnostics \
  --resource /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault} \
  --logs '[{"category": "AuditEvent", "enabled": true}]' \
  --workspace /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.OperationalInsights/workspaces/{workspace}
```

Query signing operations:
```kql
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where OperationName == "VaultSign"
| project TimeGenerated, CallerIPAddress, ResultType, DurationMs
| order by TimeGenerated desc
```

### Common Issues

#### 1. Permission Denied

**Symptom**: `403 Forbidden` errors when signing tokens

**Solution**: Verify managed identity has `crypto/sign` and `keys/get` permissions:

```bash
az role assignment list \
  --assignee $AUTH_PRINCIPAL_ID \
  --scope /subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault-name}
```

#### 2. Circuit Breaker Open

**Symptom**: Errors like `Circuit breaker is OPEN`

**Cause**: Multiple consecutive failures to Key Vault

**Solution**: 
1. Check Key Vault service health
2. Verify network connectivity from Container Apps to Key Vault
3. Wait for circuit breaker timeout (default: 60 seconds)

#### 3. Key Not Found

**Symptom**: `Key not found: jwt-signing-key`

**Solution**: Verify key exists and auth service has `keys/get` permission:

```bash
az keyvault key show \
  --vault-name my-vault \
  --name jwt-signing-key
```

## Migration from Local to Key Vault Signing

### Step 1: Prepare Key Vault

1. Create RSA/EC key in Key Vault
2. Grant auth service managed identity permissions
3. Verify connectivity from Container Apps to Key Vault

### Step 2: Test in Non-Production

1. Deploy to dev/staging environment with Key Vault signing
2. Verify JWKS endpoint serves correct public key
3. Test token minting and validation
4. Monitor latency and error rates

### Step 3: Production Deployment

1. Update Container Apps environment variables:
   ```bash
   JWT_SIGNER_TYPE=keyvault
   JWT_KEY_VAULT_URL=https://prod-vault.vault.azure.net/
   JWT_KEY_VAULT_KEY_NAME=jwt-signing-key
   ```
2. Deploy with rolling update (zero downtime)
3. Monitor metrics and logs
4. If issues occur, rollback by setting `JWT_SIGNER_TYPE=local`

### Step 4: Remove Secrets

After successful migration and verification period:

1. Remove `jwt_private_key` secret from Key Vault secrets
2. Keep `jwt_public_key` for backward compatibility (validation only)

## Security Best Practices

1. **Use HSM-Backed Keys**: For compliance requirements, use Premium Key Vault with HSM-backed keys
2. **Enable Soft Delete**: Protect against accidental key deletion
3. **Enable Purge Protection**: Prevent permanent key deletion during retention period
4. **Rotate Keys Regularly**: Establish a key rotation schedule (e.g., every 90 days)
5. **Monitor Access**: Set up alerts for unauthorized access attempts
6. **Use Private Endpoints**: For production, connect Container Apps to Key Vault via private endpoints
7. **Separate Vaults**: Use separate vaults for dev/staging/prod environments

## Cost Considerations

### Key Vault Pricing

- **Standard Vault**: $0.03 per 10,000 transactions
- **Premium Vault** (HSM-backed): $1/key/month + $0.03 per 10,000 transactions

### Example Cost Calculation

For 1 million token minting operations per month:

- **Signing operations**: 1,000,000 
- **Public key retrievals** (JWKS): ~100,000 (cached aggressively)
- **Total transactions**: ~1,100,000
- **Cost**: $0.03 × 110 = $3.30/month (Standard) or $1 + $3.30 = $4.30/month (Premium)

**Note**: This is minimal compared to the security and operational benefits.

## References

- [Azure Key Vault Documentation](https://docs.microsoft.com/azure/key-vault/)
- [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [JWK RFC 7517](https://datatracker.ietf.org/doc/html/rfc7517)
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
