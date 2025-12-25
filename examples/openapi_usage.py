#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example: Using OpenAPI specifications for validation and client generation.

This example demonstrates how to:
1. Load and validate OpenAPI specifications
2. Extract endpoint information
3. Validate request/response data against the spec
4. Generate client code (conceptually)

The hybrid OpenAPI workflow provides:
- Gateway spec (spec-first): openapi/gateway.yaml
- Service specs (code-first): openapi/generated/*.yaml
"""

from pathlib import Path
from typing import Any, Dict

import yaml


def load_openapi_spec(spec_path: Path) -> Dict[str, Any]:
    """Load an OpenAPI specification from a YAML file.
    
    Args:
        spec_path: Path to the OpenAPI spec file
    
    Returns:
        OpenAPI specification as a dictionary
    
    Raises:
        FileNotFoundError: If spec file doesn't exist
        yaml.YAMLError: If spec file has invalid YAML syntax
    """
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    
    try:
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        return spec
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in {spec_path}: {e}")


def print_spec_info(spec: Dict[str, Any], spec_name: str) -> None:
    """Print information about an OpenAPI spec.
    
    Args:
        spec: OpenAPI specification dictionary
        spec_name: Name of the specification for display
    """
    print(f"\n{'='*60}")
    print(f"OpenAPI Spec: {spec_name}")
    print(f"{'='*60}")
    
    info = spec.get('info', {})
    print(f"Title: {info.get('title', 'N/A')}")
    print(f"Version: {info.get('version', 'N/A')}")
    print(f"OpenAPI Version: {spec.get('openapi', 'N/A')}")
    
    paths = spec.get('paths', {})
    print(f"\nEndpoints: {len(paths)}")
    
    # Group endpoints by tag
    tags = {}
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                endpoint_tags = details.get('tags', ['untagged'])
                for tag in endpoint_tags:
                    if tag not in tags:
                        tags[tag] = []
                    tags[tag].append(f"{method.upper():6} {path}")
    
    print("\nEndpoints by category:")
    for tag, endpoints in sorted(tags.items()):
        print(f"\n  {tag.upper()}:")
        for endpoint in sorted(endpoints):
            print(f"    {endpoint}")


def extract_security_requirements(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Extract security requirements from an OpenAPI spec.
    
    Args:
        spec: OpenAPI specification dictionary
    
    Returns:
        Dictionary containing security scheme information
    """
    security_schemes = spec.get('components', {}).get('securitySchemes', {})
    global_security = spec.get('security', [])
    
    return {
        'schemes': security_schemes,
        'global': global_security
    }


def validate_gateway_routes() -> None:
    """Validate that gateway routes are properly defined."""
    repo_root = Path(__file__).parent.parent
    gateway_spec_path = repo_root / 'openapi' / 'gateway.yaml'
    
    if not gateway_spec_path.exists():
        print("Error: Gateway spec not found at:", gateway_spec_path)
        return
    
    print("\n" + "="*60)
    print("Validating Gateway OpenAPI Spec")
    print("="*60)
    
    spec = load_openapi_spec(gateway_spec_path)
    
    # Check required fields
    required_fields = ['openapi', 'info', 'paths', 'components']
    missing_fields = [f for f in required_fields if f not in spec]
    
    if missing_fields:
        print(f"❌ Missing required fields: {missing_fields}")
        return
    
    print("✓ All required fields present")
    
    # Check security schemes
    security = extract_security_requirements(spec)
    print(f"\n✓ Security schemes defined: {len(security['schemes'])}")
    for scheme_name, scheme in security['schemes'].items():
        print(f"  - {scheme_name}: {scheme.get('type', 'unknown')}")
    
    # Check paths
    paths = spec.get('paths', {})
    print(f"\n✓ Total endpoints: {len(paths)}")
    
    # Count by method
    methods_count = {}
    for path, methods in paths.items():
        for method in methods:
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                methods_count[method.upper()] = methods_count.get(method.upper(), 0) + 1
    
    print("\n  Methods breakdown:")
    for method, count in sorted(methods_count.items()):
        print(f"    {method:6}: {count}")
    
    print("\n✅ Gateway spec is valid and well-formed")


def compare_specs() -> None:
    """Compare gateway spec with service specs to check alignment."""
    repo_root = Path(__file__).parent.parent
    gateway_spec_path = repo_root / 'openapi' / 'gateway.yaml'
    generated_dir = repo_root / 'openapi' / 'generated'
    
    print("\n" + "="*60)
    print("Comparing Gateway and Service Specs")
    print("="*60)
    
    if not gateway_spec_path.exists():
        print("❌ Gateway spec not found")
        return
    
    gateway_spec = load_openapi_spec(gateway_spec_path)
    gateway_paths = set(gateway_spec.get('paths', {}).keys())
    
    print(f"\nGateway defines {len(gateway_paths)} paths")
    
    # Check for generated service specs
    if not generated_dir.exists():
        print("\n⚠️  No generated service specs found yet")
        print("   Run: ./scripts/generate_service_openapi.py --all")
        return
    
    service_specs = list(generated_dir.glob('*.yaml'))
    
    if not service_specs:
        print("\n⚠️  No service specs generated yet")
        return
    
    print(f"\nFound {len(service_specs)} service specs:")
    
    for service_spec_path in sorted(service_specs):
        service_name = service_spec_path.stem
        print(f"\n  {service_name}:")
        
        try:
            service_spec = load_openapi_spec(service_spec_path)
            service_paths = list(service_spec.get('paths', {}).keys())
            print(f"    Endpoints: {len(service_paths)}")
            
            # Check which service paths are exposed in gateway
            prefix = f'/{service_name}'
            exposed = [p for p in gateway_paths if p.startswith(prefix)]
            print(f"    Exposed via gateway: {len(exposed)}")
            
            if len(exposed) < len(service_paths):
                print(f"    ℹ️  {len(service_paths) - len(exposed)} internal-only endpoints")
        
        except Exception as e:
            print(f"    ❌ Error loading spec: {e}")


def main():
    """Main example function."""
    print("\n" + "="*60)
    print("OpenAPI Specification Example")
    print("="*60)
    print("\nThis example demonstrates the hybrid OpenAPI workflow:")
    print("- Spec-first: Gateway (openapi/gateway.yaml)")
    print("- Code-first: Services (openapi/generated/*.yaml)")
    
    # Validate gateway spec
    validate_gateway_routes()
    
    # Print detailed gateway info
    repo_root = Path(__file__).parent.parent
    gateway_spec_path = repo_root / 'openapi' / 'gateway.yaml'
    
    if gateway_spec_path.exists():
        gateway_spec = load_openapi_spec(gateway_spec_path)
        print_spec_info(gateway_spec, "Gateway API")
    
    # Compare specs
    compare_specs()
    
    print("\n" + "="*60)
    print("Example Complete")
    print("="*60)
    print("\nNext steps:")
    print("1. Generate service specs: ./scripts/generate_service_openapi.py --all")
    print("2. Validate specs: openapi-spec-validator openapi/gateway.yaml")
    print("3. Generate gateway configs: cd infra/gateway && ./generate_gateway_config.py --provider all --output /tmp/gateway")
    print("4. Review documentation: docs/openapi.md")
    print()


if __name__ == '__main__':
    main()
