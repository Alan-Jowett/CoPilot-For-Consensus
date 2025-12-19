<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# API Gateway Quick Reference

This document provides a quick reference for accessing services via the new unified API Gateway.

## Overview

All user-facing services are now accessible through a single entry point at **http://localhost:8080** with path-based routing.

## Service Access via Gateway

### Primary Access (Recommended)

| Service | Gateway URL | Description |
|---------|------------|-------------|
| Web UI | http://localhost:8080/ui/ | React-based interface |
| Reporting API | http://localhost:8080/api/ | REST API for summaries |
| Grafana | http://localhost:8080/grafana/ | Monitoring dashboards |
| Gateway Health | http://localhost:8080/health | Health check endpoint |
| Root | http://localhost:8080/ | Redirects to /ui/ |

### Optional Debug Access

| Service | Gateway URL | Description |
|---------|------------|-------------|
| Prometheus | http://localhost:8080/prometheus/ | Metrics query interface |
| RabbitMQ | http://localhost:8080/rabbitmq/ | Message queue management |

### Direct Access (Localhost Only - Debugging)

| Service | Direct URL | Note |
|---------|-----------|------|
| Reporting API | http://localhost:8090 | Localhost only |
| Web UI | http://localhost:8084 | Localhost only |
| Grafana | http://localhost:3000 | Localhost only |

## Quick Start

1. **Start the stack:**
   ```bash
   docker compose up -d
   ```

2. **Wait for services to be healthy:**
   ```bash
   docker compose ps gateway reporting ui grafana
   ```

3. **Access services via gateway:**
   ```bash
   # Health check
   curl http://localhost:8080/health
   
   # API
   curl http://localhost:8080/api/reports
   
   # Web UI (in browser)
   open http://localhost:8080/ui/
   
   # Grafana (in browser)
   open http://localhost:8080/grafana/
   ```

## Testing

Run the integration tests:

```bash
pytest tests/test_api_gateway.py -v
```

## Common API Endpoints

### Reporting API (via Gateway)

```bash
# Get all reports
curl http://localhost:8080/api/reports

# Get specific report
curl http://localhost:8080/api/reports/{report_id}

# Health check
curl http://localhost:8080/api/health
```

## Migration from Old URLs

If you were using the old direct access URLs, update them as follows:

| Old URL | New Gateway URL |
|---------|----------------|
| http://localhost:8080/api/reports | http://localhost:8080/api/reports *(unchanged)* |
| http://localhost:8084/ | http://localhost:8080/ui/ |
| http://localhost:3000/ | http://localhost:8080/grafana/ |

**Note**: Direct access to reporting is now on port 8090, but it's recommended to use the gateway at port 8080 instead.

## Production Considerations

When deploying to production:

1. **Enable TLS**: Add SSL certificates to nginx configuration
2. **Add Authentication**: Configure auth middleware at gateway level
3. **Restrict Debug Endpoints**: Disable or restrict `/prometheus/` and `/rabbitmq/` paths
4. **Update URLs**: Use your production domain instead of localhost

See `infra/nginx/README.md` for detailed production configuration examples.

## Troubleshooting

### Gateway returns 502 Bad Gateway

**Problem**: Upstream service is not running or unhealthy

**Solution**:
```bash
# Check service health
docker compose ps reporting ui grafana

# Check service logs
docker compose logs reporting
docker compose logs ui
docker compose logs grafana

# Restart services if needed
docker compose restart reporting ui grafana gateway
```

### CORS errors in browser

**Problem**: Browser blocking cross-origin requests

**Solution**: API endpoints already have CORS headers configured. If issues persist:
```bash
# Check response headers
curl -I -H "Origin: http://example.com" http://localhost:8080/api/

# Look for: Access-Control-Allow-Origin: *
```

### Grafana shows "Wrong URL" error

**Problem**: Grafana not configured for subpath

**Solution**: Verify Grafana environment variables in docker-compose.yml:
- `GF_SERVER_ROOT_URL=http://localhost:8080/grafana/`
- `GF_SERVER_SERVE_FROM_SUB_PATH=true`

## Additional Resources

- **Full Documentation**: [infra/nginx/README.md](../infra/nginx/README.md)
- **Port Reference**: [documents/EXPOSED_PORTS.md](../documents/EXPOSED_PORTS.md)
- **Architecture**: [documents/ARCHITECTURE.md](../documents/ARCHITECTURE.md)
