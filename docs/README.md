<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot-for-Consensus Documentation

Welcome to the comprehensive documentation for Copilot-for-Consensus! This directory contains all technical documentation organized by topic for easy discovery.

## 📚 Documentation Index

### 🏗️ Architecture
**Location**: [`architecture/`](./architecture/)

System design, architectural patterns, and component interactions.

- [System Overview](./architecture/overview.md) - Overall architecture and design patterns
- [Queue Architecture](./architecture/queue-architecture.md) - Message bus and queue design
- [Validation Architecture](./architecture/validation-architecture.md) - Schema validation and data integrity
- [Docker Compose Structure](./architecture/docker-compose-structure.md) - Container orchestration layout
- [Chunking Architecture](./architecture/chunking-architecture.md) - Text chunking strategy
- [Archive Store Architecture](./architecture/archive-store-architecture.md) - Archive storage design
- [Microservices Authentication](./architecture/microservices-auth.md) - Service-to-service auth

### 💻 Development
**Location**: [`development/`](./development/)

Guides for contributors and developers working on the codebase.

- [Local Development](./development/local-development.md) - Setting up your development environment
- [Building with Copilot](./development/building-with-copilot.md) - Using GitHub Copilot for development
- [Testing Strategy](./development/testing-strategy.md) - Comprehensive testing guide
- [Testing Message Bus](./development/testing-message-bus.md) - Message bus testing patterns
- [Conventions](./development/conventions.md) - Code style and documentation conventions
- [Forward Progress](./development/forward-progress.md) - Idempotency and error handling patterns
- [CI Coverage Strategy](./development/ci-coverage-strategy.md) - Test coverage in CI/CD
- [CI Test Timeouts](./development/ci-test-timeouts.md) - Managing test execution times
- [Dependency Validation](./development/dependency-validation.md) - Dependency management
- [Exception Handling Audit](./development/exception-handling-audit.md) - Error handling patterns
- [Mutable Defaults](./development/mutable-defaults.md) - Avoiding mutable default arguments

### 🚀 Operations
**Location**: [`operations/`](./operations/)

Deployment, monitoring, and operational guides.

- [Deployment Guide](./operations/deployment-guide.md) - Production deployment instructions
- [Exposed Ports](./operations/exposed-ports.md) - Network ports and security
- [Configuration](./operations/configuration.md) - Configuration management system
- [Configuration Migration](./operations/configuration-migration.md) - Config migration guide
- [Service Monitoring](./operations/service-monitoring.md) - Observability and monitoring
- [Metrics Integration](./operations/metrics-integration-guide.md) - Adding metrics to services
- [Failed Queue Operations](./operations/failed-queue-operations.md) - Handling failed messages
- [Retry Policy Dashboard Verification](./operations/retry-policy-dashboard-verification.md) - Dashboard setup
- [Gateway TLS Configuration](./operations/gateway-tls-configuration.md) - HTTPS/TLS setup
- [Ollama GPU Setup](./operations/ollama-gpu-setup.md) - NVIDIA GPU acceleration
- [Llama.cpp AMD Setup](./operations/llama-cpp-amd-setup.md) - AMD GPU support

#### Runbooks
**Location**: [`operations/runbooks/`](./operations/runbooks/)

Operational guides for troubleshooting common issues.

- [High Error Rate](./operations/runbooks/high-error-rate.md) - Diagnosing error spikes
- [High Queue Lag](./operations/runbooks/high-queue-lag.md) - Queue backlog resolution
- [Service Down](./operations/runbooks/service-down.md) - Service recovery procedures

### ✨ Features
**Location**: [`features/`](./features/)

Documentation for specific system features and capabilities.

- [Authentication](./features/authentication.md) - Auth integration and examples
- [OAuth Testing](./features/oauth-testing.md) - OAuth flow testing
- [OIDC Local Testing](./features/oidc-local-testing.md) - Local OIDC setup
- [Token Refresh on 403](./features/token-refresh-on-403.md) - Automatic token refresh
- [Token Refresh Testing](./features/token-refresh-testing.md) - Token refresh testing
- [Token Refresh Quick Reference](./features/token-refresh-quick-reference.md) - Quick reference
- [Grafana JWT Implementation](./features/grafana-jwt-implementation.md) - Grafana auth
- [Grafana JWT Testing](./features/grafana-jwt-testing.md) - Testing Grafana auth
- [Vectorstore Integration](./features/vectorstore-integration.md) - Vector database integration
- [Document Processing Observability](./features/document-processing-observability.md) - Processing metrics

### 🌐 API
**Location**: [`api/`](./api/)

API specifications and documentation.

- [OpenAPI](./api/openapi.md) - Hybrid OpenAPI 3.0 workflow guide

### 🌐 Gateway
**Location**: [`gateway/`](./gateway/)

Cloud-agnostic API Gateway documentation.

- [Overview](./gateway/overview.md) - Gateway architecture and workflow
- [Local Deployment](./gateway/local-deployment.md) - NGINX gateway for local dev
- [Azure Deployment](./gateway/azure-deployment.md) - Azure API Management
- [AWS Deployment](./gateway/aws-deployment.md) - AWS API Gateway
- [GCP Deployment](./gateway/gcp-deployment.md) - GCP Cloud Endpoints
- [Extending](./gateway/extending.md) - Adding support for new providers

### 📋 RFCs
**Location**: [`rfcs/`](./rfcs/)

Design documents and request for comments.

- [Observability RFC](./rfcs/observability-rfc.md) - Production observability strategy
- [Retry Policy](./rfcs/retry-policy.md) - Retry and backoff strategies

### 📊 Schemas
**Location**: [`schemas/`](./schemas/)

Data schemas and validation specifications.

- [Overview](./schemas/overview.md) - Schema system overview
- [Message Schemas](./schemas/message-schemas.md) - Database and event schemas
- [Versioning](./schemas/versioning.md) - Schema evolution and versioning
- Configuration schemas are available in [`schemas/configs/`](./schemas/configs/)
- Event schemas are available in [`schemas/events/`](./schemas/events/)

### 📝 Implementation Notes
**Location**: [`implementation-notes/`](./implementation-notes/)

Historical implementation summaries and session notes (for reference).

- [Auth Implementation Summary](./implementation-notes/auth-implementation-summary.md)
- [Auth Implementation Complete](./implementation-notes/auth-implementation-complete.md)
- [Auth API Integration Fix](./implementation-notes/auth-api-integration-fix.md)
- [Schema Config Implementation](./implementation-notes/schema-config-implementation-summary.md)
- [Token Refresh Implementation](./implementation-notes/token-refresh-implementation-summary.md)
- [Observability Implementation](./implementation-notes/observability-implementation-summary.md)
- [Archive Store Implementation](./implementation-notes/archive-store-implementation-summary.md)
- [Startup Requeue Implementation](./implementation-notes/startup-requeue-implementation.md)
- [Status Field Implementation](./implementation-notes/status-field-implementation.md)
- [Validation Summary](./implementation-notes/validation-summary.md)
- [Per-Message Events Migration](./implementation-notes/per-message-events-migration.md)
- [Identifier Standardization Analysis](./implementation-notes/identifier-standardization-analysis.md)
- [Session Summary: Auth Complete](./implementation-notes/session-summary-auth-complete.md)
- [OAuth Ready for Testing](./implementation-notes/oauth-ready-for-testing.txt)

## 🔍 Quick Links

### Getting Started
- [README (root)](../README.md) - Project overview
- [Local Development](./development/local-development.md) - Set up your environment
- [Architecture Overview](./architecture/overview.md) - Understand the system

### Contributing
- [CONTRIBUTING](../CONTRIBUTING.md) - Contribution guidelines
- [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) - Community standards
- [Conventions](./development/conventions.md) - Documentation standards

### Deployment
- [Deployment Guide](./operations/deployment-guide.md) - Production deployment
- [Configuration](./operations/configuration.md) - Configuration management
- [Service Monitoring](./operations/service-monitoring.md) - Monitoring setup

### Troubleshooting
- [Runbooks](./operations/runbooks/) - Operational troubleshooting guides
- [Failed Queue Operations](./operations/failed-queue-operations.md) - Queue management

## 📖 Documentation Standards

All documentation follows the conventions described in [development/conventions.md](./development/conventions.md):

- **File naming**: Use kebab-case (e.g., `local-development.md`)
- **Headers**: Include SPDX license identifier and copyright
- **Structure**: Use clear headings and table of contents for long documents
- **Links**: Use relative paths for internal links
- **Updates**: Keep documentation in sync with code changes

## 🤝 Contributing to Documentation

Found an issue or want to improve the docs? See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

When adding new documentation:
1. Place it in the appropriate subdirectory
2. Update this index with a link
3. Follow the naming conventions (kebab-case)
4. Include SPDX headers
5. Add cross-references where relevant

## 📜 License

All documentation is licensed under the MIT License. See [LICENSE](../LICENSE) for details.
