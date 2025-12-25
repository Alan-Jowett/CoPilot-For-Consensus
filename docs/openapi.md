<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# OpenAPI 3.0 Workflow Guide

This guide explains the hybrid OpenAPI 3.0 workflow used in Copilot-for-Consensus, covering both the spec-first public gateway and code-first internal services.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Spec-First: Public Gateway](#spec-first-public-gateway)
- [Code-First: Internal Services](#code-first-internal-services)
- [Local Development](#local-development)
- [CI/CD Integration](#cicd-integration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

We use a **hybrid OpenAPI 3.0 strategy** that balances stability and agility:

- **Spec-First for Public Gateway**: The `openapi/gateway.yaml` file is the canonical definition of all externally exposed endpoints, enabling cloud-native deployment
- **Code-First for Internal Services**: Internal service APIs are generated from FastAPI annotations, ensuring code and documentation stay in sync

This approach provides:
- ✅ Consistency between implementation and interface
- ✅ Cloud-native gateway deployment from a stable spec
- ✅ Contributor-friendly service development
- ✅ Automated validation preventing drift
- ✅ Service discoverability and documentation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Public API Gateway                        │
│                  (openapi/gateway.yaml)                      │
│                      Spec-First                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┬────────────┬─────────────┐
        │                   │            │             │
        ▼                   ▼            ▼             ▼
┌───────────────┐  ┌──────────────┐ ┌─────────┐ ┌──────────────┐
│   Reporting   │  │  Ingestion   │ │  Auth   │ │ Orchestrator │
│   Service     │  │   Service    │ │ Service │ │   Service    │
│  (generated)  │  │ (generated)  │ │(generated)│ │ (generated) │
│  Code-First   │  │  Code-First  │ │Code-First│ │ Code-First  │
└───────────────┘  └──────────────┘ └─────────┘ └──────────────┘
```

## Spec-First: Public Gateway

The public gateway uses a **spec-first approach** for maximum stability and cloud-provider compatibility.

### Canonical Specification

**Location**: `openapi/gateway.yaml`

This file is the single source of truth for:
- All public endpoints exposed through the gateway
- Request/response schemas
- Authentication requirements
- Rate limiting policies
- API versioning

### When to Update gateway.yaml

Update `gateway.yaml` when:
- Adding a new public endpoint
- Modifying an existing endpoint's contract
- Adding/changing authentication requirements
- Updating API metadata (version, description, etc.)

### How to Update gateway.yaml

1. **Edit the spec file**:
   ```bash
   vim openapi/gateway.yaml
   ```

2. **Validate the spec locally**:
   ```bash
   # Install validator if needed
   pip install openapi-spec-validator
   
   # Validate spec
   openapi-spec-validator openapi/gateway.yaml
   ```

3. **Test gateway generation**:
   ```bash
   cd infra/gateway
   
   # Test NGINX generation (used locally)
   ./generate_gateway_config.py --provider nginx --output /tmp/test-nginx
   
   # Test cloud provider generation
   ./generate_gateway_config.py --provider azure --output /tmp/test-azure
   ./generate_gateway_config.py --provider aws --output /tmp/test-aws
   ./generate_gateway_config.py --provider gcp --output /tmp/test-gcp
   ```

4. **Review generated configs**:
   ```bash
   # Check NGINX config
   cat /tmp/test-nginx/nginx.conf
   
   # Check Azure APIM policy
   cat /tmp/test-azure/policy.xml
   ```

5. **Commit your changes**:
   ```bash
   git add openapi/gateway.yaml
   git commit -sm "Add new endpoint to gateway spec"
   git push
   ```

CI will automatically:
- Validate the spec
- Generate all provider configs
- Upload configs as artifacts
- Fail if validation fails

### Adding a New Endpoint

Example: Adding a new `/reporting/api/stats` endpoint:

```yaml
paths:
  /reporting/api/stats:
    get:
      summary: Get system statistics
      description: Retrieve aggregate statistics across all reports
      tags:
        - reporting
      security:
        - BearerAuth: []
      responses:
        '200':
          description: System statistics
          content:
            application/json:
              schema:
                type: object
                properties:
                  total_reports:
                    type: integer
                  total_threads:
                    type: integer
                  date_range:
                    type: object
                    properties:
                      start:
                        type: string
                        format: date-time
                      end:
                        type: string
                        format: date-time
        '401':
          description: Unauthorized
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '503':
          description: Service unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
```

## Code-First: Internal Services

Internal services use a **code-first approach** where OpenAPI specs are generated from FastAPI code.

### Service Implementation

Services are implemented using FastAPI with type annotations:

```python
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Reporting Service",
    version="0.1.0",
    description="Internal API for report management"
)

class ReportResponse(BaseModel):
    """Response model for report data."""
    id: str
    thread_id: str
    summary: str
    created_at: str

@app.get("/api/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str):
    """Get a specific report by ID.
    
    Args:
        report_id: Unique identifier for the report
    
    Returns:
        Report data with summary and metadata
    """
    # Implementation...
    pass
```

FastAPI automatically:
- Generates OpenAPI spec from type annotations
- Validates request/response schemas
- Provides interactive API docs at `/docs`
- Supports both JSON and form data

### Generating Service Specs

Service specs are auto-generated from code using the `generate_service_openapi.py` script.

**Generate a single service spec**:
```bash
./scripts/generate_service_openapi.py --service reporting
```

**Generate all service specs**:
```bash
./scripts/generate_service_openapi.py --all
```

**Generate with validation**:
```bash
./scripts/generate_service_openapi.py --all --validate
```

Generated specs are stored in `openapi/generated/`:
- `openapi/generated/reporting.yaml`
- `openapi/generated/ingestion.yaml`
- `openapi/generated/auth.yaml`
- `openapi/generated/orchestrator.yaml`

### When to Regenerate Specs

Regenerate service specs when:
- Adding new endpoints to a service
- Modifying endpoint parameters or responses
- Updating service metadata (version, description)
- Before creating a PR with API changes

**Note**: CI automatically regenerates and validates all service specs on every push.

### Best Practices for Service APIs

1. **Use type annotations**:
   ```python
   @app.get("/api/reports")
   def get_reports(
       limit: int = Query(10, ge=1, le=100),
       skip: int = Query(0, ge=0)
   ) -> Dict[str, Any]:
       pass
   ```

2. **Use Pydantic models**:
   ```python
   from pydantic import BaseModel
   
   class CreateReportRequest(BaseModel):
       thread_id: str
       summary: str
   
   @app.post("/api/reports", response_model=ReportResponse)
   def create_report(request: CreateReportRequest):
       pass
   ```

3. **Document with docstrings**:
   ```python
   @app.get("/api/reports/search")
   def search_reports(topic: str = Query(..., description="Search query")):
       """Search reports by topic.
       
       Uses embedding-based similarity search to find relevant reports.
       
       Args:
           topic: Search query string
       
       Returns:
           List of matching reports with similarity scores
       """
       pass
   ```

4. **Define response models**:
   ```python
   class ErrorResponse(BaseModel):
       detail: str
       code: str
   
   @app.get(
       "/api/reports/{id}",
       response_model=ReportResponse,
       responses={
           404: {"model": ErrorResponse},
           503: {"model": ErrorResponse}
       }
   )
   def get_report(id: str):
       pass
   ```

## Local Development

### Prerequisites

```bash
# Install OpenAPI tools
pip install openapi-spec-validator pyyaml

# Or use the dev requirements
pip install -r requirements-dev.txt
```

### Validating Your Changes

**Validate gateway spec**:
```bash
openapi-spec-validator openapi/gateway.yaml
```

**Generate and validate service specs**:
```bash
# Generate all service specs
./scripts/generate_service_openapi.py --all --validate

# Check output
ls -la openapi/generated/
```

**Test gateway generation**:
```bash
cd infra/gateway

# Generate for all providers
./generate_gateway_config.py --provider all --output /tmp/gateway-test

# Check generated files
find /tmp/gateway-test -type f
```

### Testing Service APIs Locally

1. **Start services**:
   ```bash
   docker compose up -d reporting ingestion auth orchestrator gateway
   ```

2. **Access service docs**:
   - Reporting: http://localhost:8080/reporting/docs
   - Ingestion: http://localhost:8080/ingestion/docs
   - Auth: http://localhost:8080/auth/docs

3. **Test endpoints**:
   ```bash
   # Health check
   curl http://localhost:8080/reporting/health
   
   # Get reports
   curl http://localhost:8080/reporting/api/reports
   ```

### Viewing Generated Specs

FastAPI provides interactive documentation at `/docs`:

```bash
# Start reporting service
docker compose up -d reporting gateway

# View interactive docs
xdg-open http://localhost:8080/reporting/docs

# Download OpenAPI spec
curl http://localhost:8080/reporting/openapi.json > reporting-spec.json
```

## CI/CD Integration

The OpenAPI workflow is integrated into CI/CD via `.github/workflows/openapi-validation.yml`.

### What CI Does

1. **Validate Gateway Spec**:
   - Syntax validation with `openapi-spec-validator`
   - YAML structure validation
   - Required field validation

2. **Generate Provider Configs**:
   - NGINX (local deployment)
   - Azure APIM (Azure cloud)
   - AWS API Gateway (AWS cloud)
   - GCP API Gateway (GCP cloud)

3. **Validate Generated Configs**:
   - NGINX syntax check
   - Provider-specific validation
   - Route matching verification

4. **Generate Service Specs**:
   - Extract OpenAPI specs from all services
   - Validate generated specs
   - Check for missing or invalid specs

5. **Upload Artifacts**:
   - Provider gateway configs
   - Generated service specs
   - Validation reports

### CI Workflow Triggers

The workflow runs on:
- Pull requests modifying:
  - `openapi/**`
  - `infra/gateway/**`
  - Service `main.py` files
  - CI workflow files

- Pushes to `main` branch with same paths

### Handling CI Failures

**Gateway spec validation failed**:
```
Fix: openapi-spec-validator openapi/gateway.yaml
Check: Required fields, syntax errors, invalid references
```

**Gateway generation failed**:
```
Fix: cd infra/gateway && ./generate_gateway_config.py --provider <provider> --output /tmp/test
Check: Provider adapter compatibility, OpenAPI version
```

**Service spec generation failed**:
```
Fix: ./scripts/generate_service_openapi.py --service <service> --validate
Check: Service imports, FastAPI app definition, type annotations
```

**Service spec validation failed**:
```
Fix: Check service endpoint definitions, response models, parameter types
Review: FastAPI docs at /<service>/docs for generated spec
```

## Best Practices

### For Gateway Spec (gateway.yaml)

1. **Keep it stable**: The gateway spec should change infrequently
2. **Version your API**: Use semantic versioning in `info.version`
3. **Document thoroughly**: Add descriptions for all endpoints and parameters
4. **Use references**: Share common schemas via `$ref` in `components.schemas`
5. **Security first**: Define security schemes and apply them consistently
6. **Test before committing**: Validate and generate configs locally

### For Service APIs (FastAPI)

1. **Annotate everything**: Use type hints on all parameters and return values
2. **Use Pydantic models**: Define request/response models for complex data
3. **Write docstrings**: Document endpoint behavior, parameters, and responses
4. **Handle errors**: Define error response models and status codes
5. **Keep it internal**: Internal services don't need the same stability as public APIs
6. **Regenerate regularly**: Check generated specs when making changes

### For Both

1. **Validate early**: Run validation locally before pushing
2. **Review generated output**: Check what the tools generate
3. **Document changes**: Explain API changes in commit messages and PRs
4. **Version appropriately**: Bump versions when making breaking changes
5. **Monitor CI**: Fix failures quickly to unblock other work

## Troubleshooting

### "OpenAPI spec validation failed"

**Problem**: Spec has syntax errors or missing required fields

**Solution**:
```bash
# Check spec syntax
openapi-spec-validator openapi/gateway.yaml

# Common issues:
# - Missing 'openapi', 'info', or 'paths' fields
# - Invalid $ref references
# - Malformed YAML syntax
```

### "Gateway generation failed"

**Problem**: Adapter can't generate config from spec

**Solution**:
```bash
# Test locally
cd infra/gateway
./generate_gateway_config.py --provider <provider> --output /tmp/test

# Check adapter compatibility
# Review provider-specific requirements in docs/gateway/<provider>-deployment.md
```

### "Service spec generation failed"

**Problem**: Can't import service or extract OpenAPI spec

**Solution**:
```bash
# Check service can be imported
python -c "from <service>.main import app; print(app.openapi())"

# Common issues:
# - Missing dependencies (install service requirements.txt)
# - Service initialization errors
# - Missing FastAPI app instance
```

### "Generated spec out of date"

**Problem**: CI detects service spec doesn't match code

**Solution**:
```bash
# Regenerate specs
./scripts/generate_service_openapi.py --all

# Commit updated specs
git add openapi/generated/
git commit -sm "Update generated service specs"
```

### "NGINX configuration test failed"

**Problem**: Generated NGINX config has syntax errors

**Solution**:
```bash
# Test NGINX config
cd infra/gateway
./generate_gateway_config.py --provider nginx --output /tmp/nginx-test

# Validate with Docker
docker run --rm -v /tmp/nginx-test/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t
```

## Additional Resources

- [Gateway Overview](gateway/overview.md) - Gateway abstraction architecture
- [Gateway Extension Guide](gateway/extending.md) - Adding new cloud providers
- [Local Deployment](gateway/local-deployment.md) - NGINX gateway setup
- [Azure Deployment](gateway/azure-deployment.md) - Azure APIM setup
- [AWS Deployment](gateway/aws-deployment.md) - AWS API Gateway setup
- [GCP Deployment](gateway/gcp-deployment.md) - GCP API Gateway setup
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - FastAPI framework docs
- [OpenAPI 3.0 Specification](https://swagger.io/specification/) - OpenAPI standard

## Contributing

When contributing API changes:

1. **Update gateway.yaml** if adding/changing public endpoints
2. **Update service code** with proper type annotations
3. **Regenerate service specs** before committing
4. **Validate locally** before pushing
5. **Document changes** in PR description
6. **Monitor CI** and fix failures promptly

For questions or issues, please:
- Open an issue on GitHub
- Discuss in pull request comments
- Check existing documentation in `docs/gateway/`
