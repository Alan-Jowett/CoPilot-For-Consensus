<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# API Gateway Abstraction

This directory contains the cloud-agnostic API gateway abstraction layer for Copilot-for-Consensus.

## Quick Links

- **OpenAPI Specification**: [`../../openapi/gateway.yaml`](../../openapi/gateway.yaml) (canonical location)
- **Documentation**: [`../../docs/openapi.md`](../../docs/openapi.md) (hybrid OpenAPI workflow)
- **Deployment Guides**: [`../../docs/gateway/`](../../docs/gateway/)

## Contents

- **`openapi.yaml`** - Legacy location (backward compatibility only) - **Use `../../openapi/gateway.yaml` instead**
- **`adapter_base.py`** - Abstract base class for gateway adapters
- **`azure_adapter.py`** - Azure API Management adapter
- **`aws_adapter.py`** - AWS API Gateway adapter
- **`gcp_adapter.py`** - GCP Cloud Endpoints adapter
- **`generate_gateway_config.py`** - Configuration generator CLI tool

## Quick Start

### Generate Gateway Configuration

```bash
# Generate configuration for a specific provider
./generate_gateway_config.py --provider azure --output ../../dist/gateway/azure
./generate_gateway_config.py --provider aws --output ../../dist/gateway/aws
./generate_gateway_config.py --provider gcp --output ../../dist/gateway/gcp

# Generate all provider configurations
./generate_gateway_config.py --provider all --output ../../dist/gateway
```

### Test the Generator

```bash
# Install dependencies
pip install pyyaml

# Generate NGINX validation
./generate_gateway_config.py --provider nginx --output /tmp/gateway-test

# View validation report
cat /tmp/gateway-test/nginx_validation_report.txt
```

## Architecture

```
OpenAPI Spec (openapi.yaml)
         │
         ├─→ NginxAdapter     → NGINX config validation
         ├─→ AzureAdapter     → ARM/Bicep templates
         ├─→ AwsAdapter       → CloudFormation/SAM templates
         └─→ GcpAdapter       → Cloud Endpoints config
```

## Usage Patterns

### 1. Adding a New Endpoint

1. Update `openapi.yaml` with the new path:
   ```yaml
   paths:
     /new-service/api/endpoint:
       get:
         summary: New endpoint
         tags:
           - new-service
   ```

2. Update backend routing in `x-gateway-config`:
   ```yaml
   x-gateway-config:
     backends:
       new-service:
         url: http://new-service:8000
         health-check: /health
   ```

3. Regenerate provider configurations:
   ```bash
   ./generate_gateway_config.py --provider all --output ../../dist/gateway
   ```

4. Update NGINX config (`../nginx/nginx.conf`) to match:
   ```nginx
   location /new-service/ {
       proxy_pass http://new-service:8000/;
   }
   ```

### 2. Validating NGINX Configuration

```bash
# Generate validation report
./generate_gateway_config.py --provider nginx --output /tmp/validation

# Compare with actual nginx.conf
cat /tmp/validation/nginx_validation_report.txt
```

### 3. Adding Provider-Specific Configuration

Use `x-` extensions in OpenAPI spec:

```yaml
paths:
  /api/endpoint:
    post:
      x-gateway-config:
        rate-limit: 10/minute
        requires-auth: true
        requires-role: admin
```

Adapters read these extensions when generating configurations.

## Extending

To add support for a new cloud provider:

1. Create `<provider>_adapter.py`:
   ```python
   from adapter_base import GatewayAdapter
   
   class NewProviderAdapter(GatewayAdapter):
       @property
       def provider_name(self) -> str:
           return "newprovider"
       
       # Implement required methods
   ```

2. Register in `generate_gateway_config.py`:
   ```python
   from newprovider_adapter import NewProviderAdapter
   
   adapters = {
       'newprovider': NewProviderAdapter,
       # ... existing adapters
   }
   ```

3. Test the adapter:
   ```bash
   ./generate_gateway_config.py --provider newprovider --output /tmp/test
   ```

See [Extending Guide](../../docs/gateway/extending.md) for details.

## Documentation

Full documentation available in `docs/gateway/`:

- **[Overview](../../docs/gateway/overview.md)** - Architecture and workflow
- **[Local Deployment](../../docs/gateway/local-deployment.md)** - NGINX gateway guide
- **[Azure Deployment](../../docs/gateway/azure-deployment.md)** - Azure APIM guide
- **[AWS Deployment](../../docs/gateway/aws-deployment.md)** - AWS API Gateway guide
- **[GCP Deployment](../../docs/gateway/gcp-deployment.md)** - GCP Cloud Endpoints guide
- **[Extending](../../docs/gateway/extending.md)** - How to add new adapters

## OpenAPI Specification

The `openapi.yaml` file defines all public endpoints, authentication, and routing configuration. Key sections:

- **`info`**: API metadata and version
- **`servers`**: Default server URLs
- **`paths`**: Endpoint definitions with methods and parameters
- **`components`**: Reusable schemas, security schemes, parameters
- **`x-gateway-config`**: Custom extension for gateway-specific settings
  - `backends`: Backend service URLs
  - `cors`: CORS policy
  - `rate-limiting`: Default rate limits
  - `observability`: Metrics, tracing, logging settings

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Validate OpenAPI Spec
  run: |
    pip install openapi-spec-validator
    openapi-spec-validator infra/gateway/openapi.yaml

- name: Generate Gateway Configs
  run: |
    cd infra/gateway
    pip install pyyaml
    ./generate_gateway_config.py --provider all --output ../../dist/gateway

- name: Upload Artifacts
  uses: actions/upload-artifact@v3
  with:
    name: gateway-configs
    path: dist/gateway/
```

## Dependencies

### Python Packages

- **PyYAML**: OpenAPI spec parsing (required)
- **openapi-spec-validator**: Spec validation (optional, for CI)

Install:
```bash
pip install pyyaml openapi-spec-validator
```

### Provider CLIs (Optional)

For validating generated configurations:

- **Azure CLI**: `az` command
- **AWS CLI**: `aws` command
- **GCP CLI**: `gcloud` command

## Testing

Run basic tests:

```bash
# Test NGINX adapter
./generate_gateway_config.py --provider nginx --output /tmp/test-nginx
test -f /tmp/test-nginx/nginx_validation_report.txt && echo "✓ NGINX adapter works"

# Test Azure adapter
./generate_gateway_config.py --provider azure --output /tmp/test-azure
test -f /tmp/test-azure/azure-apim-template.json && echo "✓ Azure adapter works"

# Test AWS adapter
./generate_gateway_config.py --provider aws --output /tmp/test-aws
test -f /tmp/test-aws/aws-api-gateway-template.json && echo "✓ AWS adapter works"

# Test GCP adapter
./generate_gateway_config.py --provider gcp --output /tmp/test-gcp
test -f /tmp/test-gcp/gcp-openapi-spec.yaml && echo "✓ GCP adapter works"
```

## Troubleshooting

### "Module not found" Error

Install dependencies:
```bash
pip install pyyaml
```

### OpenAPI Validation Failed

Check YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('openapi.yaml'))"
```

### Generated Config Invalid

- Ensure backend URLs are set in `x-gateway-config.backends`
- Check provider-specific requirements
- Validate with provider CLI tools

## Support

- Review [documentation](../../docs/gateway/)
- Check OpenAPI spec for errors
- Open GitHub issue with generator output and error logs
