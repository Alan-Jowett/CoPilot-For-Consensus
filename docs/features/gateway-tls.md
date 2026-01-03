<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Gateway TLS Configuration

HTTPS-only gateway on port 443 with support for self-signed (development) and production certificates.

## Quick Start

### Development (Self-Signed Certificates)

```bash
./scripts/generate_gateway_certs.sh
docker compose up -d gateway

# Test HTTPS (ignore self-signed warnings)
curl -k https://localhost/health
```

### Production (CA-Signed Certificates)

```bash
# Copy your CA-signed certificates
cp /path/to/your/server.crt ./secrets/gateway_tls_cert
cp /path/to/your/server.key ./secrets/gateway_tls_key
chmod 644 ./secrets/gateway_tls_cert
chmod 600 ./secrets/gateway_tls_key

# Start gateway
docker compose up -d gateway

# Test HTTPS
curl https://localhost/health
```

## How It Works

Docker Compose mounts certificate files from `./secrets/` into the container:
- `./secrets/gateway_tls_cert` → `/etc/nginx/certs/server.crt`
- `./secrets/gateway_tls_key` → `/etc/nginx/certs/server.key`

Gateway entrypoint script:
- If files exist (mounted or from secrets) → use them
- If files don't exist → generate self-signed certificates
- Configure NGINX to use HTTPS on port 8443 (mapped to host port 443)

## Testing

**With self-signed certificates**:
```bash
curl -k https://localhost/health
```

**Production certificates** (no `-k` flag needed):
```bash
curl https://localhost/health
```

**With certificate details**:
```bash
curl -k -v https://localhost/health
```

## Certificate Requirements

- **Format**: PEM-encoded X.509 certificate and private key
- **Permissions**: Cert `644`, key `600` (restrictive for private key)
- **Expiration**: Keep track of renewal dates (add to calendar)
- **Subject**: CN should match your domain (e.g., `CN=consensus.example.com`)

## Renewal

For production certificates, set up renewal reminders. Options:
- **Let's Encrypt + Certbot**: Automatic renewal with systemd timer
- **Manual**: Calendar reminder 30 days before expiration
- **Azure App Service**: Automatic renewal via managed certificates

See [docs/gateway/overview.md](../gateway/overview.md) for full gateway deployment and configuration.
