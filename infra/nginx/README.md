<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# NGINX API Gateway Configuration

This directory contains the NGINX configuration for the API Gateway service, which provides a unified entry point for all microservices in the Copilot-for-Consensus stack.

## Overview

The API Gateway consolidates all user-facing services under a single port (8080) with distinct URI prefixes, simplifying deployment, networking, and external integration.

## Features

- **Unified Port**: All services accessible via port 8080
- **Path-based Routing**: Services mapped to logical URI prefixes
- **CORS Support**: Configured for cross-origin requests to API endpoints
- **WebSocket Support**: Enables Grafana live updates
- **Health Checks**: Gateway-level health endpoint
- **Compression**: Gzip compression for improved performance

## Routing Configuration

| Path | Target Service | Internal Port | Purpose |
|------|---------------|---------------|---------|
| `/` | Redirect to `/ui/` | - | Default landing page |
| `/api/` | reporting | 8080 | REST API for summaries and reports |
| `/ui/` | ui | 80 | React-based web interface |
| `/grafana/` | grafana | 3000 | Monitoring dashboards and logs |
| `/prometheus/` | monitoring | 9090 | Metrics query interface (debugging) |
| `/rabbitmq/` | messagebus | 15672 | Message queue management UI (debugging) |
| `/health` | Gateway | - | Gateway health check endpoint |

## Configuration Files

### nginx.conf

Main NGINX configuration file with:
- **Upstream definitions**: Service discovery via Docker DNS
- **Server block**: Listener on port 8080
- **Location blocks**: Path-based routing rules
- **Proxy settings**: Headers, timeouts, and error handling
- **CORS headers**: Configured for API endpoints

## Usage

### Starting the Gateway

The gateway is automatically started as part of the docker-compose stack:

```bash
docker compose up -d gateway
```

### Accessing Services

Via the unified gateway (recommended):
```bash
curl http://localhost:8080/health          # Gateway health check
curl http://localhost:8080/api/reports     # Reporting API
curl http://localhost:8080/ui/             # Web UI
curl http://localhost:8080/grafana/        # Grafana dashboards
```

Direct access (localhost only, for debugging):
```bash
curl http://localhost:8090/health          # Reporting service direct
curl http://localhost:8084/                # UI direct
curl http://localhost:3000/                # Grafana direct
```

### Testing the Configuration

To validate the NGINX configuration syntax (note: will fail on upstream resolution without running services):

```bash
docker run --rm -v $PWD/infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t
```

To test with the full stack running:

```bash
# Start all services
docker compose up -d

# Test gateway endpoints
curl -f http://localhost:8080/health
curl -f http://localhost:8080/api/
curl -f http://localhost:8080/ui/
curl -f http://localhost:8080/grafana/
```

### Viewing Logs

Gateway access and error logs:

```bash
# Access logs
docker compose logs gateway

# Follow logs in real-time
docker compose logs -f gateway

# Last 100 lines
docker compose logs --tail=100 gateway
```

## Security Considerations

### Current Configuration

- **No TLS**: HTTP only (suitable for local development)
- **No Authentication**: All endpoints publicly accessible
- **CORS Enabled**: Allows cross-origin requests to `/api/`

### Production Recommendations

1. **Enable TLS**: Add SSL/TLS certificates and configure HTTPS
   ```nginx
   listen 443 ssl http2;
   ssl_certificate /etc/nginx/ssl/cert.pem;
   ssl_certificate_key /etc/nginx/ssl/key.pem;
   ```

2. **Add Authentication**: Configure auth middleware
   ```nginx
   location /api/ {
       auth_basic "Copilot API";
       auth_basic_user_file /etc/nginx/.htpasswd;
       proxy_pass http://reporting/api/;
   }
   ```

3. **Restrict Admin Endpoints**: Limit `/prometheus/` and `/rabbitmq/` to specific IPs
   ```nginx
   location /prometheus/ {
       allow 10.0.0.0/8;  # Internal network only
       deny all;
       proxy_pass http://prometheus/;
   }
   ```

4. **Rate Limiting**: Protect against abuse
   ```nginx
   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
   
   location /api/ {
       limit_req zone=api burst=20;
       proxy_pass http://reporting/api/;
   }
   ```

5. **Request Logging**: Enhanced logging for security auditing
   ```nginx
   log_format detailed '$remote_addr - $remote_user [$time_local] '
                      '"$request" $status $body_bytes_sent '
                      '"$http_referer" "$http_user_agent" '
                      '$request_time $upstream_response_time';
   access_log /var/log/nginx/access.log detailed;
   ```

## Customization

### Adding a New Service

1. Add upstream definition:
   ```nginx
   upstream myservice {
       server myservice:8080;
   }
   ```

2. Add location block:
   ```nginx
   location /myservice/ {
       proxy_pass http://myservice/;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   }
   ```

3. Update docker-compose.yml gateway dependencies:
   ```yaml
   gateway:
     depends_on:
       myservice:
         condition: service_healthy
   ```

### Modifying Timeouts

For long-running requests (e.g., LLM inference):

```nginx
location /api/summarize/ {
    proxy_pass http://reporting/api/summarize/;
    proxy_read_timeout 300s;  # 5 minutes
    proxy_send_timeout 300s;
}
```

## Troubleshooting

### Gateway Not Starting

Check logs for configuration errors:
```bash
docker compose logs gateway
```

Common issues:
- **Syntax error**: Run `nginx -t` to validate configuration
- **Upstream unavailable**: Ensure dependent services are healthy
- **Port conflict**: Verify port 8080 is not in use

### 502 Bad Gateway

Indicates upstream service is unreachable:

1. Check upstream service health:
   ```bash
   docker compose ps reporting ui grafana
   ```

2. Verify internal DNS resolution:
   ```bash
   docker compose exec gateway ping -c 1 reporting
   docker compose exec gateway ping -c 1 ui
   ```

3. Check upstream service logs:
   ```bash
   docker compose logs reporting
   ```

### CORS Issues

If browser shows CORS errors:

1. Verify CORS headers in response:
   ```bash
   curl -H "Origin: http://example.com" -I http://localhost:8080/api/reports
   ```

2. Check `Access-Control-Allow-Origin` header is present
3. Ensure `add_header` directives are in correct location block

## See Also

- [EXPOSED_PORTS.md](../../documents/EXPOSED_PORTS.md): Port security and access control
- [ARCHITECTURE.md](../../documents/ARCHITECTURE.md): System architecture overview
- [docker-compose.yml](../../docker-compose.yml): Service orchestration configuration
