<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Extending the Gateway Abstraction

This guide explains how to add support for new cloud providers or gateway platforms to the Copilot-for-Consensus gateway abstraction.

## Overview

The gateway abstraction is designed to be extensible. Adding a new provider requires:

1. Creating an adapter class that implements `GatewayAdapter`
2. Registering the adapter in the generator
3. Testing the adapter
4. Documenting the deployment process

## Step 1: Create an Adapter Class

### Basic Structure

Create a new file `infra/gateway/<provider>_adapter.py`:

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""<Provider> Gateway adapter for gateway configuration."""

import json
from pathlib import Path
from typing import Any, Dict

from adapter_base import GatewayAdapter


class MyProviderAdapter(GatewayAdapter):
    """Adapter for <Provider Name>.

    Generates:
    - Configuration format 1
    - Configuration format 2
    - Deployment scripts
    """

    @property
    def provider_name(self) -> str:
        return "myprovider"

    @property
    def deployment_instructions(self) -> str:
        return """
<Provider> Deployment Instructions:
===================================

Prerequisites:
- List prerequisites here

Deployment Steps:

1. First step...
2. Second step...
3. etc.

Monitoring:
- How to monitor the deployment
"""

    def load_spec(self) -> None:
        """Load the OpenAPI specification from YAML file."""
        import yaml

        with open(self.openapi_spec_path, 'r') as f:
            self.openapi_spec = yaml.safe_load(f)

    def validate_spec(self) -> bool:
        """Validate OpenAPI spec for this provider."""
        # Check required fields
        required_fields = ['openapi', 'info', 'paths']
        for field in required_fields:
            if field not in self.openapi_spec:
                raise ValueError(f"OpenAPI spec missing required field: {field}")

        # Check OpenAPI version compatibility
        version = self.openapi_spec.get('openapi', '')
        if not version.startswith('3.'):
            raise ValueError(f"Provider requires OpenAPI 3.x, got {version}")

        return True

    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate provider-specific gateway configuration."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate your configuration files
        config1 = self._generate_main_config()
        config1_path = output_dir / "main-config.json"
        with open(config1_path, 'w') as f:
            json.dump(config1, f, indent=2)

        # Generate additional files as needed
        script = self._generate_deploy_script()
        script_path = output_dir / "deploy.sh"
        with open(script_path, 'w') as f:
            f.write(script)
        script_path.chmod(0o755)

        return {
            "main_config": config1_path,
            "deploy_script": script_path
        }

    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate generated configuration files."""
        # Check files exist
        for file_path in config_files.values():
            if not file_path.exists():
                raise ValueError(f"Generated file does not exist: {file_path}")

        # Add provider-specific validation
        # For example, validate JSON structure, required fields, etc.

        return True

    def _generate_main_config(self) -> Dict[str, Any]:
        """Generate the main configuration structure."""
        info = self.openapi_spec.get('info', {})

        # Transform OpenAPI spec to provider's format
        return {
            "name": info.get('title', 'API Gateway'),
            "version": info.get('version', '1.0.0'),
            "routes": self._extract_routes()
        }

    def _extract_routes(self) -> list:
        """Extract routes from OpenAPI spec."""
        routes = []
        for path, methods in self.openapi_spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    routes.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": operation.get('summary', ''),
                    })
        return routes

    def _generate_deploy_script(self) -> str:
        """Generate deployment script."""
        return """#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

set -e

echo "Deploying to <Provider>..."

# Add deployment commands here

echo "Deployment complete!"
"""
```

### Required Methods

Your adapter **must** implement these methods:

| Method | Returns | Purpose |
|--------|---------|---------|
| `provider_name` | `str` | Unique identifier for the provider |
| `deployment_instructions` | `str` | Human-readable deployment guide |
| `load_spec()` | `None` | Load and parse OpenAPI specification |
| `validate_spec()` | `bool` | Validate spec compatibility |
| `generate_config()` | `Dict[str, Path]` | Generate all config files |
| `validate_config()` | `bool` | Validate generated files |

### Helper Methods

Create private helper methods for:
- Transforming OpenAPI spec to provider format
- Generating specific configuration sections
- Creating deployment artifacts
- Extracting backend routes

## Step 2: Register the Adapter

Edit `infra/gateway/generate_gateway_config.py`:

```python
from adapter_base import GatewayAdapter, NginxAdapter
from azure_adapter import AzureAdapter
from aws_adapter import AwsAdapter
from gcp_adapter import GcpAdapter
from myprovider_adapter import MyProviderAdapter  # Add import


def get_adapter(provider: str, openapi_spec_path: Path) -> GatewayAdapter:
    """Get the appropriate adapter for the provider."""
    adapters = {
        'nginx': NginxAdapter,
        'azure': AzureAdapter,
        'aws': AwsAdapter,
        'gcp': GcpAdapter,
        'myprovider': MyProviderAdapter,  # Register adapter
    }

    # ... rest of function
```

Also update the CLI choices:

```python
parser.add_argument(
    '--provider',
    type=str,
    required=True,
    choices=['nginx', 'azure', 'aws', 'gcp', 'myprovider', 'all'],  # Add choice
    help='Target cloud provider (or "all" for all providers)'
)
```

And update the all-providers list:

```python
if args.provider == 'all':
    providers = ['nginx', 'azure', 'aws', 'gcp', 'myprovider']  # Add provider
```

## Step 3: Test the Adapter

### Manual Testing

```bash
cd infra/gateway

# Test adapter generation
./generate_gateway_config.py --provider myprovider --output /tmp/test-myprovider

# Verify generated files
ls -la /tmp/test-myprovider/

# Check file contents
cat /tmp/test-myprovider/main-config.json
```

### Validation Tests

Test the following scenarios:

1. **Valid OpenAPI spec**: Should generate successfully
2. **Missing required fields**: Should raise ValueError
3. **Incompatible version**: Should raise ValueError
4. **Empty paths**: Should generate but with no routes
5. **Complex routes**: Test with nested paths, parameters, etc.

Example test script:

```python
#!/usr/bin/env python3
"""Test MyProvider adapter."""

import sys
from pathlib import Path
import tempfile

# Add gateway directory to path
sys.path.insert(0, str(Path(__file__).parent))

from myprovider_adapter import MyProviderAdapter


def test_basic_generation():
    """Test basic configuration generation."""
    spec_path = Path(__file__).parent / "openapi.yaml"
    adapter = MyProviderAdapter(spec_path)

    # Load and validate
    adapter.load_spec()
    assert adapter.validate_spec()

    # Generate config
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        config_files = adapter.generate_config(output_dir)

        # Verify files were created
        assert len(config_files) > 0
        for path in config_files.values():
            assert path.exists()
            assert path.stat().st_size > 0

        # Validate generated config
        assert adapter.validate_config(config_files)

    print("✓ Basic generation test passed")


if __name__ == '__main__':
    test_basic_generation()
    print("✅ All tests passed!")
```

Run the test:

```bash
python test_myprovider_adapter.py
```

## Step 4: Document the Provider

### Create Deployment Guide

Create `docs/gateway/<provider>-deployment.md`:

```markdown
# <Provider> Gateway Deployment

## Overview

Brief description of the provider and why you'd use it.

## Prerequisites

- List all prerequisites
- Include accounts, CLIs, permissions needed

## Architecture

Diagram or description of how the gateway works on this provider.

## Deployment Steps

### Step 1: Prepare Configuration

```bash
cd infra/gateway
./generate_gateway_config.py --provider myprovider --output ../../dist/gateway/myprovider
```

### Step 2: Review Generated Files

List and explain each generated file.

### Step 3: Deploy

Detailed deployment commands and explanation.

### Step 4: Verify

How to verify the deployment succeeded.

### Step 5: Test

How to test the deployed gateway.

## Configuration Options

Explain customizable parameters and how to set them.

## Monitoring and Logging

How to access logs and metrics.

## Troubleshooting

Common issues and solutions.

## Cost Considerations

Pricing model and cost optimization tips.

## Security Best Practices

Security recommendations for this provider.

## Additional Resources

Links to provider documentation, examples, etc.
```

### Update Main Documentation

Add your provider to `docs/gateway/overview.md`:

1. Add to the deployment targets section
2. Add to configuration workflow examples
3. Add to CI/CD integration examples

## Step 5: Add CI/CD Integration (Optional)

Add validation to `.github/workflows/gateway-validation.yml`:

```yaml
- name: Test MyProvider adapter
  run: |
    cd infra/gateway
    ./generate_gateway_config.py --provider myprovider --output /tmp/test-myprovider
    test -f /tmp/test-myprovider/main-config.json
```

## Step 6: Submit for Review

1. Create a pull request with:
   - Adapter implementation
   - Tests and validation
   - Documentation
   - Example generated configurations

2. Include in PR description:
   - Why this provider was added
   - How to test it
   - Link to provider documentation
   - Any limitations or caveats

## Example: Kubernetes Ingress Adapter

Here's a concrete example for Kubernetes Ingress:

```python
class KubernetesAdapter(GatewayAdapter):
    """Adapter for Kubernetes Ingress resources."""

    @property
    def provider_name(self) -> str:
        return "kubernetes"

    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate Kubernetes manifests."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate Ingress resource
        ingress = {
            'apiVersion': 'networking.k8s.io/v1',
            'kind': 'Ingress',
            'metadata': {
                'name': 'copilot-gateway',
                'annotations': {
                    'nginx.ingress.kubernetes.io/rewrite-target': '/$2'
                }
            },
            'spec': {
                'rules': self._generate_ingress_rules()
            }
        }

        import yaml
        ingress_path = output_dir / "ingress.yaml"
        with open(ingress_path, 'w') as f:
            yaml.dump(ingress, f)

        return {"ingress": ingress_path}

    def _generate_ingress_rules(self) -> list:
        """Generate Ingress rules from OpenAPI paths."""
        rules = []
        gateway_config = self.openapi_spec.get('x-gateway-config', {})
        backends = gateway_config.get('backends', {})

        for service, config in backends.items():
            rules.append({
                'host': 'copilot.example.com',
                'http': {
                    'paths': [{
                        'path': f'/{service}(/|$)(.*)',
                        'pathType': 'Prefix',
                        'backend': {
                            'service': {
                                'name': service,
                                'port': {
                                    'number': self._extract_port(config['url'])
                                }
                            }
                        }
                    }]
                }
            })

        return rules

    def _extract_port(self, url: str) -> int:
        """Extract port from backend URL."""
        # Parse URL and return port
        import re
        match = re.search(r':(\d+)', url)
        return int(match.group(1)) if match else 80
```

## Best Practices

### 1. Use OpenAPI Extensions Wisely

Only add provider-specific extensions if absolutely necessary:

```yaml
paths:
  /api/endpoint:
    post:
      x-myprovider-config:
        special-feature: enabled
```

### 2. Handle Missing Configuration Gracefully

Provide defaults when optional configuration is missing:

```python
gateway_config = self.openapi_spec.get('x-gateway-config', {})
backends = gateway_config.get('backends', {})
default_backend = backends.get('default', {'url': 'http://localhost:8080'})
```

### 3. Generate Human-Readable Output

Include comments, documentation, and examples in generated files:

```python
def _generate_config(self):
    return f"""# Generated configuration for {self.provider_name}
# Date: {datetime.now().isoformat()}
# Source: {self.openapi_spec_path}

# Configuration follows
config:
  name: {self.openapi_spec['info']['title']}
  ...
"""
```

### 4. Validate Early and Often

Validate at multiple stages:
- OpenAPI spec syntax
- Provider compatibility
- Generated file structure
- Deployment prerequisites

### 5. Provide Clear Error Messages

```python
def validate_spec(self) -> bool:
    if 'info' not in self.openapi_spec:
        raise ValueError(
            "OpenAPI spec missing 'info' section. "
            "This provider requires API title and version metadata."
        )
    return True
```

## Common Patterns

### Pattern 1: Route Extraction

```python
def _extract_routes(self) -> list:
    """Extract routes from OpenAPI paths."""
    routes = []
    for path, methods in self.openapi_spec.get('paths', {}).items():
        for method, operation in methods.items():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                route = {
                    'path': path,
                    'method': method.upper(),
                    'backend': self._determine_backend(path),
                    'security': operation.get('security', []),
                }
                routes.append(route)
    return routes

def _determine_backend(self, path: str) -> str:
    """Determine backend service from path."""
    if path.startswith('/reporting'):
        return 'reporting'
    elif path.startswith('/ingestion'):
        return 'ingestion'
    # ... etc
    return 'default'
```

### Pattern 2: Template Generation

```python
def _generate_from_template(self, template_name: str, context: dict) -> str:
    """Generate config from Jinja2 template."""
    from jinja2 import Template

    template_path = Path(__file__).parent / 'templates' / template_name
    with open(template_path) as f:
        template = Template(f.read())

    return template.render(**context)
```

### Pattern 3: Multi-File Generation

```python
def generate_config(self, output_dir: Path) -> Dict[str, Path]:
    """Generate multiple related configuration files."""
    files = {}

    # Main configuration
    files['main'] = self._generate_file(
        output_dir / 'main.yaml',
        self._generate_main_config()
    )

    # Backend configurations (one per service)
    backends_dir = output_dir / 'backends'
    backends_dir.mkdir(exist_ok=True)

    for service, config in self._get_backends().items():
        files[f'backend_{service}'] = self._generate_file(
            backends_dir / f'{service}.yaml',
            config
        )

    return files

def _generate_file(self, path: Path, content: Any) -> Path:
    """Helper to write content to file."""
    import yaml
    with open(path, 'w') as f:
        yaml.dump(content, f)
    return path
```

## Testing Checklist

Before submitting your adapter:

- [ ] Adapter implements all required methods
- [ ] Adapter is registered in generator
- [ ] OpenAPI spec loads successfully
- [ ] Spec validation works correctly
- [ ] Configuration generation produces valid files
- [ ] Generated files pass validation
- [ ] Deployment instructions are clear and complete
- [ ] Documentation is comprehensive
- [ ] Example configurations are included
- [ ] Tests pass for all scenarios
- [ ] Error messages are helpful
- [ ] Code follows project style guidelines

## Support

Questions about extending the gateway abstraction?

- Review existing adapters for examples
- Check the [Gateway Overview](./overview.md)
- Open a GitHub discussion for design questions
- Submit a draft PR for feedback

Good luck building your adapter! 🚀
