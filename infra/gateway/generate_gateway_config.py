#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Gateway configuration generator.

This script generates cloud-provider-specific gateway configurations
from the canonical OpenAPI specification.

Usage:
    ./generate_gateway_config.py --provider nginx --output dist/gateway/nginx
    ./generate_gateway_config.py --provider azure --output dist/gateway/azure
    ./generate_gateway_config.py --provider aws --output dist/gateway/aws
    ./generate_gateway_config.py --provider gcp --output dist/gateway/gcp
    ./generate_gateway_config.py --provider all --output dist/gateway
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
# This ensures the script can find adapter modules when run from any directory
script_dir = Path(__file__).parent.resolve()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from adapter_base import GatewayAdapter, NginxAdapter
from azure_adapter import AzureAdapter
from aws_adapter import AwsAdapter
from gcp_adapter import GcpAdapter


def get_adapter(provider: str, openapi_spec_path: Path) -> GatewayAdapter:
    """Get the appropriate adapter for the provider.
    
    Args:
        provider: Provider name (nginx, azure, aws, gcp)
        openapi_spec_path: Path to OpenAPI specification
    
    Returns:
        GatewayAdapter instance for the provider
    
    Raises:
        ValueError: If provider is not supported
    """
    adapters = {
        'nginx': NginxAdapter,
        'azure': AzureAdapter,
        'aws': AwsAdapter,
        'gcp': GcpAdapter,
    }
    
    adapter_class = adapters.get(provider.lower())
    if not adapter_class:
        raise ValueError(
            f"Unsupported provider: {provider}. "
            f"Supported providers: {', '.join(adapters.keys())}"
        )
    
    return adapter_class(openapi_spec_path)


def generate_for_provider(
    provider: str,
    openapi_spec_path: Path,
    output_dir: Path,
    validate: bool = True
) -> None:
    """Generate gateway configuration for a specific provider.
    
    Args:
        provider: Provider name (nginx, azure, aws, gcp)
        openapi_spec_path: Path to OpenAPI specification
        output_dir: Directory for generated files
        validate: Whether to validate the generated configuration
    """
    print(f"\n{'='*60}")
    print(f"Generating configuration for: {provider.upper()}")
    print(f"{'='*60}\n")
    
    # Get adapter
    adapter = get_adapter(provider, openapi_spec_path)
    
    # Load and validate spec
    print("📖 Loading OpenAPI specification...")
    adapter.load_spec()
    
    print("✅ Validating OpenAPI specification...")
    try:
        adapter.validate_spec()
        print("   ✓ Specification is valid")
    except ValueError as e:
        print(f"   ✗ Validation failed: {e}")
        sys.exit(1)
    
    # Generate configuration
    print(f"\n🔧 Generating {provider} configuration...")
    try:
        config_files = adapter.generate_config(output_dir)
        print(f"   ✓ Generated {len(config_files)} file(s)")
        for artifact_type, file_path in config_files.items():
            print(f"     - {artifact_type}: {file_path}")
    except Exception as e:
        print(f"   ✗ Generation failed: {e}")
        sys.exit(1)
    
    # Validate generated configuration
    if validate:
        print(f"\n🔍 Validating generated configuration...")
        try:
            adapter.validate_config(config_files)
            print("   ✓ Configuration is valid")
        except ValueError as e:
            print(f"   ✗ Validation failed: {e}")
            sys.exit(1)
    
    # Print deployment instructions
    print(f"\n📚 Deployment Instructions:")
    print("-" * 60)
    print(adapter.deployment_instructions)
    print("-" * 60)
    
    print(f"\n✅ Successfully generated {provider} configuration!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate cloud-provider gateway configurations from OpenAPI spec',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate NGINX configuration
  ./generate_gateway_config.py --provider nginx --output dist/gateway/nginx
  
  # Generate Azure APIM configuration
  ./generate_gateway_config.py --provider azure --output dist/gateway/azure
  
  # Generate all provider configurations
  ./generate_gateway_config.py --provider all --output dist/gateway
  
  # Skip validation (faster, but not recommended)
  ./generate_gateway_config.py --provider aws --output dist/gateway/aws --no-validate
        """
    )
    
    parser.add_argument(
        '--provider',
        type=str,
        required=True,
        choices=['nginx', 'azure', 'aws', 'gcp', 'all'],
        help='Target cloud provider (or "all" for all providers)'
    )
    
    parser.add_argument(
        '--spec',
        type=Path,
        default=Path(__file__).parent / 'openapi.yaml',
        help='Path to OpenAPI specification (default: openapi.yaml)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for generated configuration'
    )
    
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip validation of generated configuration'
    )
    
    args = parser.parse_args()
    
    # Check that OpenAPI spec exists
    if not args.spec.exists():
        print(f"Error: OpenAPI specification not found: {args.spec}")
        sys.exit(1)
    
    print(f"\n🌐 Gateway Configuration Generator")
    print(f"OpenAPI Spec: {args.spec}")
    print(f"Output Directory: {args.output}")
    
    # Generate for specified provider(s)
    if args.provider == 'all':
        providers = ['nginx', 'azure', 'aws', 'gcp']
        for provider in providers:
            provider_output = args.output / provider
            generate_for_provider(
                provider,
                args.spec,
                provider_output,
                validate=not args.no_validate
            )
    else:
        generate_for_provider(
            args.provider,
            args.spec,
            args.output,
            validate=not args.no_validate
        )
    
    print(f"\n✨ All configurations generated successfully!")
    print(f"   Output directory: {args.output}")


if __name__ == '__main__':
    main()
