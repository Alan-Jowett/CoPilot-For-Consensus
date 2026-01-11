<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Local NGINX Gateway Deployment

## Overview

The NGINX-based API Gateway is the **default and recommended** deployment method for local development, testing, and single-machine deployments. It provides a simple, containerized reverse proxy that unifies all Copilot-for-Consensus services under a single endpoint.

## Features

- ✅ **Zero cloud dependencies** - Runs entirely offline
- ✅ **Docker Compose integration** - Single command deployment
- ✅ **TLS/HTTPS support** - Self-signed or custom certificates
- ✅ **Health checks** - Built-in endpoint monitoring
- ✅ **Path-based routing** - Clean URL structure
- ✅ **JWT token forwarding** - Seamless authentication
- ✅ **Static content serving** - Web UI and documentation

## Architecture

```
                        ┌─────────────────────┐
                        │   API Gateway       │
                        │   (NGINX:443)       │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
    ┌─────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
    │  Reporting:8080  │  │ Ingestion:8001 │  │   Auth:8090     │
    └──────────────────┘  └────────────────┘  └─────────────────┘
              │                    │                     │
    ┌─────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
    │      UI:80       │  │ Grafana:3000   │  │  (other svcs)   │
    └──────────────────┘  └────────────────┘  └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Ports 443 and 8080 available (or configure alternatives)
- Secrets configured (see main README.md)

### 1. Start All Services

```bash
# Start infrastructure and application services
docker compose up -d

# The gateway will automatically:
# - Generate self-signed TLS certificates (if not provided)
# - Configure HTTPS on port 443
# - Start proxying requests to backend services
```

### 2. Verify Gateway Health

```bash
# HTTP health check
curl http://localhost:8080/health

# HTTPS health check (ignore self-signed cert warning)
curl -k https://localhost:443/health
```

Expected response:
```
ok
```

### 3. Access Services

| Service | HTTP URL | HTTPS URL |
|---------|----------|-----------|
| Web UI | http://localhost:8080/ui/ | https://localhost:443/ui/ |
| Reporting API | http://localhost:8080/reporting/ | https://localhost:443/reporting/ |
| Auth Service | http://localhost:8080/auth/ | https://localhost:443/auth/ |
| Ingestion API | http://localhost:8080/ingestion/ | https://localhost:443/ingestion/ |
| Grafana | http://localhost:8080/grafana/ | https://localhost:443/grafana/ |

### 4. Test an Endpoint

```bash
# Get reports via gateway
curl http://localhost:8080/reporting/api/reports

# Or via HTTPS
curl -k https://localhost:443/reporting/api/reports
```

## Configuration

### Ports

The gateway exposes two ports by default:
- **Port 443**: HTTPS (recommended for production-like testing)
- **Port 8080**: HTTP (internal, not exposed in production Docker Compose)

To change ports, edit `docker-compose.infra.yml`:

```yaml
gateway:
  ports:
    - "0.0.0.0:443:8443"  # External:Internal
```

### TLS Certificates

#### Option 1: Self-Signed (Default)

The gateway automatically generates self-signed certificates on startup if none are provided:

```bash
docker compose up -d gateway
```

Certificates are generated with:
- Common Name: `localhost`
- Valid for: 365 days
- RSA 2048-bit key

#### Option 2: Custom Certificates

Provide your own certificates via Docker secrets:

1. Place certificate files:
   ```bash
   cp /path/to/cert.pem secrets/gateway_tls_cert
   cp /path/to/key.pem secrets/gateway_tls_key
   ```

2. Start the gateway:
   ```bash
   docker compose up -d gateway
   ```

The gateway will detect and use your certificates automatically.

#### Option 3: Let's Encrypt (Advanced)

For production deployments with a real domain:

1. Use Certbot to obtain certificates:
   ```bash
   certbot certonly --standalone -d your-domain.com
   ```

2. Copy to secrets:
   ```bash
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem secrets/gateway_tls_cert
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem secrets/gateway_tls_key
   sudo chown $USER:$USER secrets/gateway_tls_*
   ```

3. Update NGINX config with your domain and restart gateway

### Routes and Backends

Routes are defined in `infra/nginx/nginx.conf`. The configuration matches the OpenAPI specification in `infra/gateway/openapi.yaml`.

**Current Routes**:

```nginx
/                     -> Redirect to /ui/
/health               -> Gateway health check
/reporting/*          -> reporting:8080
/ingestion/*          -> ingestion:8001
/auth/*               -> auth:8090
/admin/*              -> auth:8090/admin
/grafana/*            -> grafana:3000
/ui/*                 -> ui:80
```

To validate that routes match the OpenAPI spec:

```bash
cd infra/gateway
./generate_gateway_config.py --provider nginx --output ../../dist/gateway/nginx
cat ../../dist/gateway/nginx/nginx_validation_report.txt
```

### CORS Configuration

CORS is handled by individual backend services. The gateway forwards all headers and doesn't add CORS headers itself.

For development, services are configured with permissive CORS by default.

### Request Limits

Default NGINX limits:
- **Max body size**: 1M (can be increased in nginx.conf)
- **Timeouts**: 65s keepalive
- **Connections**: 1024 per worker

To increase body size for file uploads:

```nginx
server {
    client_max_body_size 100M;  # Add to server block
    ...
}
```

## Monitoring

### Access Logs

View real-time access logs:

```bash
docker compose logs -f gateway
```

Log format includes:
- Client IP
- Request method and path
- Response status code
- Response time

### Health Checks

The gateway container includes a health check that runs every 10 seconds:

```bash
# Check gateway health status
docker compose ps gateway

# Manual health check
curl http://localhost:8080/health
```

### Backend Service Status

Check status of backend services through the gateway:

```bash
# Reporting service
curl http://localhost:8080/reporting/health

# Ingestion service
curl http://localhost:8080/ingestion/health

# Auth service
curl http://localhost:8080/auth/health
```

## Troubleshooting

### Gateway Won't Start

**Symptom**: `docker compose up gateway` fails

**Solutions**:
1. Check port availability:
   ```bash
   # Linux/macOS
   sudo lsof -i :443
   sudo lsof -i :8080

   # Windows
   netstat -ano | findstr :443
   netstat -ano | findstr :8080
   ```

2. Check logs:
   ```bash
   docker compose logs gateway
   ```

3. Verify NGINX config syntax:
   ```bash
   docker compose run --rm gateway nginx -t
   ```

### 502 Bad Gateway

**Symptom**: Gateway returns 502 errors

**Cause**: Backend service not ready or crashed

**Solutions**:
1. Check backend service status:
   ```bash
   docker compose ps
   ```

2. Check backend health:
   ```bash
   # Direct access (bypassing gateway)
   curl http://localhost:8080/reporting/health
   ```

3. Check backend logs:
   ```bash
   docker compose logs reporting
   docker compose logs ingestion
   docker compose logs auth
   ```

4. Restart backend service:
   ```bash
   docker compose restart reporting
   ```

### Certificate Errors

**Symptom**: Browser shows security warning

**Cause**: Self-signed certificate not trusted

**Solutions**:
1. Accept the risk (development only)
2. Add certificate to OS trust store
3. Use custom trusted certificate

**Chrome/Edge**: Click "Advanced" → "Proceed to localhost (unsafe)"
**Firefox**: Click "Advanced" → "Accept the Risk and Continue"

### Route Not Found (404)

**Symptom**: Valid endpoint returns 404

**Solutions**:
1. Verify route exists in nginx.conf:
   ```bash
   grep -A 5 "location /your-path" infra/nginx/nginx.conf
   ```

2. Check OpenAPI spec:
   ```bash
   grep "your-path" infra/gateway/openapi.yaml
   ```

3. Validate NGINX config:
   ```bash
   docker compose exec gateway nginx -t
   docker compose restart gateway
   ```

## Advanced Configuration

### Custom NGINX Modules

The gateway uses the official `nginx:alpine` image. To add modules:

1. Create custom Dockerfile:
   ```dockerfile
   FROM nginx:alpine
   RUN apk add --no-cache nginx-mod-http-geoip2
   COPY nginx.conf /etc/nginx/nginx.conf
   ```

2. Update `docker-compose.infra.yml`:
   ```yaml
   gateway:
     build:
       context: ./infra/nginx
       dockerfile: Dockerfile.custom
   ```

### Rate Limiting

Add rate limiting to nginx.conf:

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        location /reporting/api/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://reporting:8080/api/;
        }
    }
}
```

### Load Balancing

For multiple backend instances:

```nginx
http {
    upstream reporting_backend {
        server reporting-1:8080;
        server reporting-2:8080;
        server reporting-3:8080;
    }

    server {
        location /reporting/ {
            proxy_pass http://reporting_backend/;
        }
    }
}
```

### Basic Authentication

Add basic auth to protect endpoints:

```nginx
server {
    location /admin/ {
        auth_basic "Admin Area";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://auth:8090/admin/;
    }
}
```

Create password file:
```bash
docker compose exec gateway sh
apk add apache2-utils
htpasswd -c /etc/nginx/.htpasswd admin
```

## Production Considerations

For production single-machine deployments:

1. **Use proper TLS certificates** (Let's Encrypt or commercial CA)
2. **Restrict exposed ports** (close HTTP port 8080, use only HTTPS)
3. **Enable request logging** to file or log aggregator
4. **Configure log rotation** to prevent disk space issues
5. **Set up monitoring** with Prometheus + Grafana
6. **Implement rate limiting** to prevent abuse
7. **Use strong security headers** (CSP, HSTS, etc.)
8. **Keep NGINX updated** (`docker compose pull gateway`)

## Migration to Cloud Gateway

When ready to migrate to a cloud-native gateway:

1. Generate cloud provider configuration:
   ```bash
   cd infra/gateway
   ./generate_gateway_config.py --provider azure --output ../../dist/gateway/azure
   ```

2. Deploy to cloud provider (see provider-specific guides)

3. Update DNS records to point to cloud gateway

4. Test cloud gateway thoroughly

5. Decommission local gateway (or keep for development)

The OpenAPI specification ensures consistent behavior across all deployment targets.

## Additional Resources

- [Gateway Overview](./overview.md) - Architecture and design
- [OpenAPI Specification](../../infra/gateway/openapi.yaml) - API definition
- [NGINX Configuration](../../infra/nginx/nginx.conf) - Route definitions
- [Docker Compose Setup](../../docker-compose.infra.yml) - Service orchestration

## Support

For issues with the local gateway:
- Check logs: `docker compose logs gateway`
- Verify config: `docker compose exec gateway nginx -t`
- Review documentation: [docs/gateway/](.)
- Open GitHub issue with logs and config details
