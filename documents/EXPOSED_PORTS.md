<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Exposed Ports Reference

This document describes all network ports exposed by the Copilot-for-Consensus Docker Compose stack, their purpose, security considerations, and access recommendations.

## Port Security Strategy

The Docker Compose configuration follows a **principle of least exposure**:

1. **Public Exposure (0.0.0.0)**: Only user-facing services that require external network access
2. **Localhost-only (127.0.0.1)**: Development and debugging services accessible only from the host machine
3. **No Port Mapping**: Internal-only services that communicate exclusively via Docker networks

## Publicly Exposed Ports (0.0.0.0)

These ports are accessible from any network interface and may be reachable from external networks depending on your firewall configuration.

### Port 3000 - Grafana (Monitoring Dashboards)

- **Service**: `grafana`
- **Purpose**: Web UI for viewing metrics dashboards and logs
- **Protocol**: HTTP
- **Access**: http://localhost:3000
- **Credentials**: admin/admin (default, should be changed in production)
- **Security Notes**: 
  - Primary monitoring interface for operators
  - Contains sensitive operational data
  - Should be protected by authentication (configured by default)
  - Consider using reverse proxy with TLS in production

### Port 8080 - Reporting API

- **Service**: `reporting`
- **Purpose**: REST API for accessing document summaries, consensus reports, and thread metadata
- **Protocol**: HTTP
- **Access**: http://localhost:8080
- **Endpoints**: `/api/reports`, `/api/threads`, `/health`
- **Security Notes**:
  - **WARNING**: No authentication or authorization implemented
  - **DO NOT** expose to untrusted networks or production environments without additional security
  - Primary API for integration with external systems
  - Consider API gateway with authentication for production deployments

## Localhost-Only Ports (127.0.0.1)

These ports are bound to localhost and only accessible from the host machine. They are not reachable from external networks.

### Port 27017 - MongoDB (Document Database)

- **Service**: `documentdb`
- **Purpose**: MongoDB database for messages, threads, summaries, and metadata
- **Protocol**: MongoDB wire protocol
- **Access**: mongodb://root:example@localhost:27017/admin
- **Use Cases**: 
  - Database administration via MongoDB Compass or mongosh
  - Direct queries for debugging
  - Data export/import operations
- **Security Notes**:
  - Contains all application data
  - Credentials stored in environment variables
  - Localhost binding prevents external database access

### Port 5672 & 15672 - RabbitMQ (Message Bus)

- **Service**: `messagebus`
- **Purpose**: 
  - Port 5672: AMQP protocol for message publishing/consuming
  - Port 15672: Management UI for queue inspection and monitoring
- **Protocol**: AMQP (5672), HTTP (15672)
- **Access**: 
  - AMQP: amqp://guest:guest@localhost:5672
  - Management UI: http://localhost:15672
- **Use Cases**:
  - Queue monitoring and debugging
  - Manual message publishing for testing
  - Dead-letter queue inspection
- **Security Notes**:
  - Contains message processing state
  - Management UI provides administrative controls
  - Localhost binding prevents external message injection

### Port 6333 - Qdrant (Vector Database)

- **Service**: `vectorstore`
- **Purpose**: Vector similarity search for semantic document retrieval
- **Protocol**: HTTP/gRPC
- **Access**: http://localhost:6333
- **Use Cases**:
  - Vector database administration
  - Collection inspection and debugging
  - Manual vector search queries
- **Security Notes**:
  - Contains document embeddings (derived from sensitive data)
  - API provides full read/write access
  - Localhost binding prevents unauthorized vector queries

### Port 11434 - Ollama (LLM Runtime)

- **Service**: `ollama`
- **Purpose**: Local LLM inference for embeddings and text generation
- **Protocol**: HTTP
- **Access**: http://localhost:11434
- **Use Cases**:
  - Model management (pull, list, delete)
  - Direct LLM inference for testing
  - Model performance monitoring
- **Security Notes**:
  - Provides access to LLM capabilities
  - Can be resource-intensive if misused
  - Localhost binding prevents external LLM usage

### Port 9090 - Prometheus (Metrics Storage)

- **Service**: `monitoring`
- **Purpose**: Metrics collection, storage, and querying
- **Protocol**: HTTP
- **Access**: http://localhost:9090
- **Use Cases**:
  - Direct metric queries (PromQL)
  - Target health monitoring
  - Alert rule debugging
- **Security Notes**:
  - Contains operational metrics (can reveal system behavior)
  - Provides read access to all collected metrics
  - Typically accessed via Grafana; direct access for debugging only

### Port 3100 - Loki (Log Aggregation)

- **Service**: `loki`
- **Purpose**: Centralized log storage and querying
- **Protocol**: HTTP
- **Access**: http://localhost:3100
- **Use Cases**:
  - Direct log queries (LogQL)
  - Log ingestion debugging
  - Typically accessed via Grafana
- **Security Notes**:
  - Contains application logs (may include sensitive information)
  - Localhost binding prevents external log access

### Port 8000 - Ingestion Service

- **Service**: `ingestion`
- **Purpose**: HTTP API for triggering ingestion jobs
- **Protocol**: HTTP
- **Access**: http://localhost:8000
- **Endpoints**: `/health`, `/ingest` (if exposed)
- **Use Cases**:
  - Manual ingestion triggering for testing
  - Health checks during development
- **Security Notes**:
  - **WARNING**: No authentication implemented
  - Can trigger resource-intensive ingestion operations
  - Localhost binding prevents unauthorized ingestion triggers

### Port 8084 - Web UI

- **Service**: `ui`
- **Purpose**: React SPA for browsing reports and managing data
- **Protocol**: HTTP
- **Access**: http://localhost:8084
- **Use Cases**:
  - Human-readable report browsing
  - Summary verification
  - UI access to reporting API
- **Security Notes**:
  - **WARNING**: No authentication or authorization implemented
  - **DO NOT** expose to untrusted networks
  - Intended for local development and demonstration only
  - Static assets served via nginx container

## Internal-Only Services (No Port Mapping)

These services communicate exclusively via Docker internal networks and are not accessible from the host machine or external networks.

### Metric Exporters (Prometheus Scrapers)

These services expose metrics that are scraped by Prometheus. They do not require host access:

- **mongodb-exporter** (internal port 9216): MongoDB metrics
- **mongo-doc-count-exporter** (internal port 9500): Custom MongoDB document count metrics
- **document-processing-exporter** (internal port 9502): Document processing pipeline metrics
- **qdrant-exporter** (internal port 9501): Qdrant vector store metrics
- **cadvisor** (internal port 8080): Container resource metrics
- **pushgateway** (internal port 9091): Prometheus Pushgateway for batch job metrics

All metrics are accessible via Prometheus at http://localhost:9090 and visualized in Grafana.

### Processing Services

These services communicate via RabbitMQ message bus and do not expose HTTP endpoints externally:

- **parsing**: Email parsing and normalization
- **chunking**: Message chunking for embedding
- **embedding**: Vector embedding generation
- **orchestrator**: Workflow coordination and RAG
- **summarization**: LLM-powered summarization

All services expose internal health check endpoints (port 8000) accessible only within the Docker network.

## Production Deployment Considerations

When deploying to production environments:

### Network Security

1. **Reverse Proxy**: Use nginx, Traefik, or cloud load balancers for TLS termination and authentication
2. **Firewall Rules**: Restrict access to public ports (3000, 8080) using firewall rules
3. **VPN/Bastion**: Access localhost-only ports via VPN or bastion host
4. **Network Segmentation**: Isolate Docker networks from untrusted networks

### Authentication & Authorization

1. **Grafana**: Configure SSO, LDAP, or OAuth for authentication
2. **Reporting API**: Implement API keys, JWT tokens, or OAuth
3. **Reporting UI**: Add authentication layer (reverse proxy with auth, or application-level auth)
4. **RabbitMQ**: Change default credentials, use TLS for AMQP connections
5. **MongoDB**: Use strong passwords, enable authentication, consider TLS

### Monitoring & Auditing

1. **Access Logs**: Enable and monitor access logs for all HTTP services
2. **Audit Trail**: Log all administrative actions (database changes, queue operations)
3. **Alerting**: Configure alerts for unauthorized access attempts
4. **Metrics**: Monitor unusual traffic patterns or access from unexpected sources

### Port Binding Changes

For production, consider removing all localhost-only port bindings and accessing services via:

- **Kubernetes**: Use kubectl port-forward for administrative access
- **Cloud Platforms**: Use cloud-native debugging tools (AWS SSM, Azure Bastion)
- **VPN**: Require VPN connection for administrative access

## Validation Commands

### Check Bound Ports

```bash
# List all listening ports from Docker containers
docker compose ps --format '{{.Name}}\t{{.Ports}}'

# Check what's listening on the host
netstat -tuln | grep -E ':(3000|8080|27017|5672|15672|6333|11434|9090|3100|8000|8084)'
# Or on Linux
ss -tuln | grep -E ':(3000|8080|27017|5672|15672|6333|11434|9090|3100|8000|8084)'
```

### Test Localhost Binding

```bash
# These should succeed (from host machine)
curl http://localhost:3000
curl http://localhost:8080/health
curl http://localhost:27017  # Will fail with MongoDB protocol error, but connection succeeds

# These should fail from external machines (connection refused or timeout)
curl http://<host-ip>:27017
curl http://<host-ip>:5672
```

### Verify Internal Services

```bash
# Check Prometheus targets to verify exporters are reachable
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Verify internal service-to-service communication
docker compose exec parsing curl -f http://messagebus:15672/api/health
docker compose exec embedding curl -f http://vectorstore:6333/collections
```

## Security Checklist

Before deploying:

- [ ] Changed default credentials for all services (Grafana, RabbitMQ, MongoDB)
- [ ] Reviewed and restricted port bindings for your environment
- [ ] Configured firewall rules to limit access to public ports
- [ ] Implemented authentication for Reporting API and UI
- [ ] Enabled TLS for external-facing services
- [ ] Configured monitoring and alerting for security events
- [ ] Reviewed logs for unauthorized access attempts
- [ ] Documented approved access methods for operations team
- [ ] Tested access controls from untrusted networks
- [ ] Established incident response procedures for security events

## See Also

- [ARCHITECTURE.md](../documents/ARCHITECTURE.md): System architecture and service interactions
- [SERVICE_MONITORING.md](../documents/SERVICE_MONITORING.md): Monitoring and observability
- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md): Local development setup
- [SECURITY.md](../SECURITY.md): Security policy and vulnerability reporting
