<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# TLS Certificates Directory

This directory is used for generating TLS certificates for the API Gateway (NGINX).

## Quick Start

For local development and testing, generate self-signed certificates:

```bash
# From the project root or from this directory
./infra/nginx/certs/generate-certs.sh

# Copy certificates to secrets directory
cp ./infra/nginx/certs/server.crt ./secrets/gateway_tls_cert
cp ./infra/nginx/certs/server.key ./secrets/gateway_tls_key

# Rebuild and restart the gateway
docker compose up -d --build gateway
```

This creates self-signed certificates and configures them as Docker secrets. The gateway automatically detects the secrets and enables HTTPS on port 8443.

## Production Deployment

For production, use valid certificates from a Certificate Authority (CA):

1. Obtain certificates from your CA (e.g., Let's Encrypt, DigiCert, etc.)
2. Copy the certificate and key to the secrets directory:
   ```bash
   cp /path/to/fullchain.pem ./secrets/gateway_tls_cert
   cp /path/to/privkey.pem ./secrets/gateway_tls_key
   chmod 600 ./secrets/gateway_tls_key
   chmod 644 ./secrets/gateway_tls_cert
   ```
3. Restart the gateway:
   ```bash
   docker compose up -d --build gateway
   ```

## How It Works

The API Gateway uses Docker secrets for TLS certificates:
- Certificates are provided as `gateway_tls_cert` and `gateway_tls_key` secrets
- The gateway container's entrypoint script checks for these secrets
- If secrets are present, HTTPS is automatically enabled on port 8443
- If secrets are absent, only HTTP is available on port 8080

This approach ensures:
- Private keys are never committed to version control
- Certificates can be rotated without rebuilding the image
- The same image works for both HTTP-only and HTTPS configurations

## Certificate Requirements

- **Format**: PEM format
- **Key Size**: Minimum 2048-bit RSA or 256-bit ECDSA
- **Certificate Chain**: Include intermediate certificates if required by your CA

## Security Notes

- **Never commit private keys** to version control (protected by `.gitignore`)
- Certificates are provided via Docker secrets (mounted at `/run/secrets/`)
- Keep private keys secure with appropriate file permissions (600)
- Rotate certificates before expiration
- Use strong key sizes (2048-bit RSA minimum, 4096-bit recommended)

## Let's Encrypt Example

Using Certbot:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy to secrets directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./secrets/gateway_tls_cert
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./secrets/gateway_tls_key
sudo chown $USER:$USER ./secrets/gateway_tls_*
chmod 644 ./secrets/gateway_tls_cert
chmod 600 ./secrets/gateway_tls_key

# Restart gateway
docker compose up -d --build gateway
```

## Troubleshooting

### HTTPS Not Working

If HTTPS is not working:
1. Check that secrets exist:
   ```bash
   ls -la ./secrets/gateway_tls_*
   ```
2. Check gateway logs:
   ```bash
   docker compose logs gateway
   ```
3. Verify certificates are valid:
   ```bash
   openssl x509 -in ./secrets/gateway_tls_cert -noout -text
   ```

### Gateway Won't Start

If the gateway fails to start after adding certificates:
1. Verify certificate format (must be PEM)
2. Check that the key matches the certificate:
   ```bash
   openssl x509 -noout -modulus -in ./secrets/gateway_tls_cert | openssl md5
   openssl rsa -noout -modulus -in ./secrets/gateway_tls_key | openssl md5
   ```
   (The MD5 hashes should match)

## References

- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [NGINX SSL/TLS Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
