# Gateway TLS Configuration

## Overview

The API Gateway runs **HTTPS-only** on port 443 for secure communication. TLS certificates are required and can be either:

1. **Self-signed** (for development/testing) - use the provided script
2. **Production** (from a Certificate Authority) - provide your own

## Quick Start

### Option 1: Generate Self-Signed Certificates (Development)

```bash
./scripts/generate_gateway_certs.sh
docker compose up -d gateway
```

Test HTTPS:

```bash
curl -k https://localhost/health  # -k ignores self-signed cert warnings
```

### Option 2: Use Your Own Certificates (Production)

```bash
# Copy your CA-signed certificates
cp /path/to/your/server.crt ./secrets/gateway_tls_cert
cp /path/to/your/server.key ./secrets/gateway_tls_key

# Set proper permissions
chmod 644 ./secrets/gateway_tls_cert
chmod 600 ./secrets/gateway_tls_key

# Start the gateway
docker compose up -d gateway
```

## How It Works

1. **Docker Compose** mounts certificate files from `./secrets/` into the container
   - `./secrets/gateway_tls_cert` → `/etc/nginx/certs/server.crt`
   - `./secrets/gateway_tls_key` → `/etc/nginx/certs/server.key`

2. **Gateway entrypoint script** checks for certificates:
   - If files exist (mounted or from secrets) → use them
   - If files don't exist → generate self-signed certificates
   - Configure nginx to use HTTPS on port 8443 (mapped to host port 443)

## Testing

### With Self-Signed Certificates

```bash
# Using curl
curl -k https://localhost/health

# Using Python
python3 -c "import requests; requests.get('https://localhost/health', verify=False)"

# Using openssl to inspect certificate
openssl x509 -in ./secrets/gateway_tls_cert -text -noout
```

### Check Certificate Details

```bash
# View certificate information
openssl x509 -in ./secrets/gateway_tls_cert -text -noout

# Check expiration date
openssl x509 -enddate -noout -in ./secrets/gateway_tls_cert

# Verify it's for localhost
openssl x509 -in ./secrets/gateway_tls_cert -noout -subject
```

## Certificate Management

### Generating New Self-Signed Certificates

```bash
# Remove old certificates
rm ./secrets/gateway_tls_cert ./secrets/gateway_tls_key

# Generate new ones
./scripts/generate_gateway_certs.sh

# Restart gateway
docker compose restart gateway
```

### Renewing Production Certificates

When your production certificate expires:

```bash
# Replace with renewed certificate from your CA
cp /path/to/renewed/cert.pem ./secrets/gateway_tls_cert
cp /path/to/renewed/key.pem ./secrets/gateway_tls_key

# Restart gateway
docker compose restart gateway
```

## Script Reference

### generate_gateway_certs.sh

Generates a self-signed TLS certificate for localhost.

**Usage:**
```bash
./scripts/generate_gateway_certs.sh
```

**Creates:**
- `./secrets/gateway_tls_cert` - X.509 certificate (2048-bit RSA)
- `./secrets/gateway_tls_key` - Private key

**Options:**
- Skips if certificates already exist
- Valid for 365 days
- Uses CN=localhost (for localhost-only testing)

## Port Mapping

- **Host**: Port 443 (standard HTTPS)
- **Container**: Port 8443 (nginx listening port)
- Mapping: `0.0.0.0:443->8443/tcp`

To use a different host port, modify `docker-compose.infra.yml`:

```yaml
ports:
  - "0.0.0.0:YOUR_PORT:8443"
```

## Security Best Practices

### Development
- Use self-signed certificates via the generation script
- Accept insecure certificate warnings in tools/clients

### Production
- Always use proper certificates from a trusted CA (e.g., Let's Encrypt)
- Set certificate permissions: `chmod 644` for cert, `chmod 600` for key
- Monitor certificate expiration and renew before expiry
- Use certificates with proper DNS names matching your domain

### General
- Never commit certificates to git - they're in `.gitignore`
- Use at least 2048-bit RSA keys (4096-bit recommended for production)
- Regularly update your certificate renewal process

## Troubleshooting

### Certificates Not Found

Check if certificate files exist:

```bash
ls -la ./secrets/gateway_tls_*
```

Generate them if missing:

```bash
./scripts/generate_gateway_certs.sh
```

### Connection Refused

1. **Verify gateway is running**:
   ```bash
   docker compose ps gateway
   ```

2. **Check logs**:
   ```bash
   docker compose logs gateway | grep -i "certificate\|tls\|error"
   ```

3. **Verify port is accessible**:
   ```bash
   sudo ss -tlnp | grep 443
   ```

### SSL Certificate Verification Errors

**For self-signed certificates (development only):**

```bash
# Ignore cert warnings
curl -k https://localhost/health

# In Python
import requests
requests.get('https://localhost/health', verify=False)

# In Node.js
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
```

**For production certificates**, use a proper CA bundle:

```bash
curl --cacert /path/to/ca.crt https://example.com/health
```

## CI/Deployment

For automated deployment:

```bash
# Generate certs as part of setup
./scripts/generate_gateway_certs.sh

# Start the stack
docker compose up -d
```

For production deployment with custom certificates:

```bash
# 1. Set up certificates from your CA
cp /secure/certs/server.crt ./secrets/gateway_tls_cert
cp /secure/certs/server.key ./secrets/gateway_tls_key
chmod 600 ./secrets/gateway_tls_key

# 2. Start the gateway
docker compose up -d gateway
```

## References

- [OpenSSL Certificate Commands](https://www.openssl.org/docs/)
- [Let's Encrypt - Free SSL Certificates](https://letsencrypt.org/)
- [NGINX TLS/SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
