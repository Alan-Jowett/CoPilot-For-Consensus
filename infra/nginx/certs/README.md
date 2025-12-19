<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# TLS Certificates Directory

This directory contains TLS certificates for the API Gateway (NGINX).

## Quick Start

For local development and testing, generate self-signed certificates:

```bash
# From the project root
./infra/nginx/certs/generate-certs.sh
```

This creates:
- `server.crt` - Self-signed certificate
- `server.key` - Private key

## Production Deployment

For production, replace the self-signed certificates with valid certificates from a Certificate Authority (CA):

1. Obtain certificates from your CA (e.g., Let's Encrypt, DigiCert, etc.)
2. Place the certificate and key files in this directory:
   - `server.crt` - Your certificate (or certificate chain)
   - `server.key` - Your private key
3. Ensure proper file permissions:
   ```bash
   chmod 600 server.key
   chmod 644 server.crt
   ```
4. Configure TLS in `.env`:
   ```bash
   GATEWAY_TLS_ENABLED=true
   ```

## Certificate Requirements

- **Format**: PEM format
- **Key Size**: Minimum 2048-bit RSA or 256-bit ECDSA
- **Certificate Chain**: Include intermediate certificates if required by your CA

## File Naming

The default names expected by the gateway configuration are:
- `server.crt` - Certificate file
- `server.key` - Private key file

These can be customized via environment variables (see `.env` file).

## Security Notes

- **Never commit private keys** to version control (protected by `.gitignore`)
- Keep private keys secure with appropriate file permissions (600)
- Rotate certificates before expiration
- Use strong key sizes (2048-bit RSA minimum, 4096-bit recommended)
- Consider using ECDSA keys for better performance

## Let's Encrypt Example

Using Certbot:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy to this directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./server.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./server.key
sudo chown $USER:$USER server.crt server.key
chmod 644 server.crt
chmod 600 server.key
```

## Troubleshooting

### Certificate Validation Errors

If you encounter certificate validation errors:
1. Verify certificate format (PEM)
2. Check certificate chain is complete
3. Ensure dates are valid (not expired)
4. Verify the key matches the certificate

### Permission Errors

If NGINX fails to read certificates:
1. Check file permissions (600 for key, 644 for certificate)
2. Ensure files are readable by the NGINX process
3. Verify SELinux context if applicable

## References

- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [NGINX SSL/TLS Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
