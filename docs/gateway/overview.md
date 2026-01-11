<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Cloud-Agnostic API Gateway Abstraction

## Overview

The Copilot-for-Consensus API Gateway provides a unified, cloud-agnostic abstraction layer for deploying the system across multiple platforms. This design enables:

- **Local Development**: NGINX-based gateway for single-machine deployments
- **Multi-Cloud**: Support for Azure, AWS, and GCP native gateways
- **Portability**: Single OpenAPI specification drives all deployments
- **Consistency**: Automated configuration generation prevents drift

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   OpenAPI Specification                      │
│                  (Canonical Source of Truth)                 │
└──────────────┬──────────────────────────────────────────────┘
               │
               │  Gateway Configuration Generator
               │
       ┌───────┴────────┬──────────┬──────────┬──────────┐
       │                │          │          │          │
       ▼                ▼          ▼          ▼          ▼
   ┌────────┐      ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ NGINX  │      │ Azure  │ │  AWS   │ │  GCP   │ │  K8s   │
   │(Local) │      │  APIM  │ │   API  │ │ Cloud  │ │Ingress │
   │        │      │        │ │Gateway │ │Endpoint│ │        │
   └────────┘      └────────┘ └────────┘ └────────┘ └────────┘
```

## Key Components

### 1. OpenAPI Specification (`openapi.yaml`)

The canonical OpenAPI 3.0 specification defines:
- All public API endpoints and methods
- Request/response schemas
- Authentication requirements
- Rate limiting policies
- CORS configuration
- Backend service routing

**Location**: `infra/gateway/openapi.yaml`

### 2. Gateway Adapters

Adapters transform the OpenAPI specification into provider-specific configurations:

- **`adapter_base.py`**: Abstract base class defining the adapter interface
- **`azure_adapter.py`**: Generates Azure API Management (ARM/Bicep) templates
- **`aws_adapter.py`**: Generates AWS API Gateway (CloudFormation/SAM) templates
- **`gcp_adapter.py`**: Generates GCP Cloud Endpoints (OpenAPI + ESPv2) configs
- **`NginxAdapter`**: Validates NGINX configuration matches OpenAPI spec

**Location**: `infra/gateway/`

### 3. Configuration Generator

Command-line tool for generating provider-specific configurations:

```bash
./infra/gateway/generate_gateway_config.py --provider <provider> --output <dir>
```

**Supported Providers**:
- `nginx` - Local NGINX deployment (validation only)
- `azure` - Azure API Management
- `aws` - AWS API Gateway
- `gcp` - GCP Cloud Endpoints
- `all` - Generate all provider configurations

## Deployment Targets

### Local Development (NGINX)

**Best For**: Single-machine development, testing, demos

**Features**:
- Simple Docker Compose deployment
- No cloud dependencies
- TLS support with self-signed certificates
- Integrated with local services

**Deployment**: See [Local Deployment Guide](./local-deployment.md)

### Azure (API Management)

**Best For**: Enterprise deployments on Azure

**Features**:
- Managed service with built-in scaling
- Azure AD integration
- Developer portal
- Analytics and monitoring

**Deployment**: See [Azure Deployment Guide](./azure-deployment.md)

### AWS (API Gateway)

**Best For**: AWS-native deployments

**Features**:
- Regional or edge-optimized endpoints
- Integration with AWS Lambda, Cognito
- CloudWatch metrics and X-Ray tracing
- WAF integration for security

**Deployment**: See [AWS Deployment Guide](./aws-deployment.md)

### GCP (Cloud Endpoints)

**Best For**: Google Cloud deployments

**Features**:
- ESPv2 proxy for Cloud Run/GKE
- Firebase authentication
- Cloud Monitoring integration
- Global load balancing

**Deployment**: See [GCP Deployment Guide](./gcp-deployment.md)

## Configuration Workflow

### 1. Update OpenAPI Specification

When adding new endpoints or changing API behavior:

1. Edit `infra/gateway/openapi.yaml`
2. Update path definitions, schemas, security requirements
3. Add provider-specific extensions if needed (`x-gateway-config`)

### 2. Generate Provider Configurations

Generate cloud-provider configurations:

```bash
cd infra/gateway

# Generate Azure configuration
./generate_gateway_config.py --provider azure --output ../../dist/gateway/azure

# Generate AWS configuration
./generate_gateway_config.py --provider aws --output ../../dist/gateway/aws

# Generate GCP configuration
./generate_gateway_config.py --provider gcp --output ../../dist/gateway/gcp

# Generate all configurations
./generate_gateway_config.py --provider all --output ../../dist/gateway
```

### 3. Validate Generated Configuration

The generator automatically validates:
- OpenAPI spec syntax and structure
- Provider compatibility
- Generated template/configuration syntax

Manual validation (optional):

```bash
# Azure ARM template
az deployment group validate \
  --resource-group <rg> \
  --template-file dist/gateway/azure/azure-apim-template.json

# AWS CloudFormation template
aws cloudformation validate-template \
  --template-body file://dist/gateway/aws/aws-api-gateway-template.json

# GCP OpenAPI spec
gcloud endpoints services deploy dist/gateway/gcp/gcp-openapi-spec.yaml --validate-only
```

### 4. Deploy to Target Platform

Follow provider-specific deployment instructions in generated files or documentation.

### 5. Update NGINX Configuration (If Needed)

If routes have changed significantly, update `infra/nginx/nginx.conf` to match the OpenAPI spec. The NGINX adapter generates a validation report to help identify discrepancies.

## CI/CD Integration

### GitHub Actions Workflow

Add to `.github/workflows/gateway-validation.yml`:

```yaml
name: Gateway Configuration Validation

on:
  pull_request:
    paths:
      - 'infra/gateway/openapi.yaml'
      - 'infra/gateway/*.py'
      - 'infra/nginx/nginx.conf'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pyyaml openapi-spec-validator

      - name: Validate OpenAPI spec
        run: |
          openapi-spec-validator infra/gateway/openapi.yaml

      - name: Generate all provider configurations
        run: |
          cd infra/gateway
          ./generate_gateway_config.py --provider all --output ../../dist/gateway

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: gateway-configs
          path: dist/gateway/
```

## Best Practices

### 1. OpenAPI as Single Source of Truth

- **Always** update the OpenAPI spec first when adding/changing endpoints
- Generate provider configs from the spec, don't manually edit them
- Use version control for the OpenAPI spec

### 2. Provider-Specific Extensions

Use `x-` prefixed extensions sparingly and document them:

```yaml
paths:
  /ingestion/api/sources:
    post:
      x-gateway-config:
        rate-limit: 10/minute
        requires-auth: true
        requires-role: admin
```

### 3. Backend URL Configuration

Keep backend URLs configurable via parameters/environment variables:

```yaml
x-gateway-config:
  backends:
    reporting:
      url: ${BACKEND_REPORTING_URL}
      health-check: /health
```

### 4. Security Considerations

- Enable authentication for sensitive endpoints
- Configure rate limiting to prevent abuse
- Use HTTPS/TLS in production
- Validate JWT tokens at the gateway
- Implement CORS policies carefully

### 5. Testing

- Test OpenAPI spec with API validation tools
- Deploy to staging environment before production
- Run integration tests against deployed gateway
- Monitor gateway metrics and logs

## Extending the Abstraction

To add support for a new provider:

1. **Create Adapter**: Implement `GatewayAdapter` in `infra/gateway/<provider>_adapter.py`
2. **Register Adapter**: Add to `adapters` dict in `generate_gateway_config.py`
3. **Document**: Create `docs/gateway/<provider>-deployment.md`
4. **Test**: Generate and deploy configuration to validate

See [Extending Guide](./extending.md) for detailed instructions.

## Troubleshooting

### OpenAPI Spec Validation Fails

Check for:
- Missing required fields (`openapi`, `info`, `paths`)
- Invalid version string (must be `3.x.x`)
- Malformed YAML syntax
- Circular references in schemas

### Generated Configuration Invalid

- Ensure backend URLs are properly configured
- Check for provider-specific limitations
- Validate with provider's CLI tools
- Review adapter-specific documentation

### NGINX Routes Don't Match OpenAPI Spec

Run the NGINX adapter to generate a validation report:

```bash
./generate_gateway_config.py --provider nginx --output dist/gateway/nginx
cat dist/gateway/nginx/nginx_validation_report.txt
```

Compare the report with `infra/nginx/nginx.conf` and update as needed.

## Additional Resources

- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [Azure API Management Documentation](https://docs.microsoft.com/azure/api-management/)
- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [GCP Cloud Endpoints Documentation](https://cloud.google.com/endpoints/docs)
- [NGINX API Gateway Patterns](https://www.nginx.com/solutions/api-management-gateway/)

## Support

For questions or issues:
- Open an issue on GitHub
- Consult provider-specific deployment guides
- Review example configurations in `dist/gateway/`
