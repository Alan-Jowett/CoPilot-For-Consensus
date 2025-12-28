<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Operations Documentation

This directory contains documentation for deploying, configuring, monitoring, and operating Copilot-for-Consensus in production environments.

## Documents

### Deployment
- **[deployment-guide.md](./deployment-guide.md)** - Production deployment instructions and best practices
- **[exposed-ports.md](./exposed-ports.md)** - Network ports reference and security considerations
- **[gateway-tls-configuration.md](./gateway-tls-configuration.md)** - HTTPS/TLS setup for the API Gateway
- **[ollama-gpu-setup.md](./ollama-gpu-setup.md)** - NVIDIA GPU acceleration setup
- **[llama-cpp-amd-setup.md](./llama-cpp-amd-setup.md)** - AMD GPU support with llama.cpp

### Configuration
- **[configuration.md](./configuration.md)** - Configuration management system overview
- **[configuration-migration.md](./configuration-migration.md)** - Guide for migrating configurations

### Monitoring & Observability
- **[service-monitoring.md](./service-monitoring.md)** - Comprehensive monitoring and observability guide
- **[metrics-integration-guide.md](./metrics-integration-guide.md)** - Adding metrics to services
- **[retry-policy-dashboard-verification.md](./retry-policy-dashboard-verification.md)** - Grafana dashboard setup

### Queue Management
- **[failed-queue-operations.md](./failed-queue-operations.md)** - Handling failed messages and queue operations

### Runbooks
**Location**: [`runbooks/`](./runbooks/)

Operational troubleshooting guides for common issues:
- **[high-error-rate.md](./runbooks/high-error-rate.md)** - Diagnosing and resolving error spikes
- **[high-queue-lag.md](./runbooks/high-queue-lag.md)** - Queue backlog resolution procedures
- **[service-down.md](./runbooks/service-down.md)** - Service recovery and restart procedures

## Related Documentation

- [Architecture](../architecture/) - System design and patterns
- [Gateway](../gateway/) - API Gateway deployment guides
- [RFCs](../rfcs/) - Design documents including observability strategy

## Purpose

These documents help operators:
- Deploy the system to production
- Configure services and infrastructure
- Monitor system health and performance
- Troubleshoot operational issues
- Maintain production systems
