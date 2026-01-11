#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generate OpenAPI specifications for internal services.

This script generates OpenAPI 3.0 specifications from FastAPI service definitions.
The generated specs are stored in openapi/generated/ and can be used for:
- Service interface documentation
- Client code generation
- Contract testing
- API compatibility validation

Usage:
    # Generate spec for a single service
    ./generate_service_openapi.py --service reporting

    # Generate specs for all services
    ./generate_service_openapi.py --all

    # Generate and validate
    ./generate_service_openapi.py --service reporting --validate
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    raise


def load_fastapi_app(service_name: str) -> Any:
    """Dynamically load FastAPI app from a service.

    Args:
        service_name: Name of the service (e.g., 'reporting', 'ingestion')

    Returns:
        FastAPI app instance

    Raises:
        ImportError: If service cannot be loaded
        AttributeError: If service does not have an 'app' attribute
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent.resolve()
    service_path = repo_root / service_name / "main.py"

    if not service_path.exists():
        raise FileNotFoundError(f"Service not found: {service_path}")

    # Load the module
    spec = importlib.util.spec_from_file_location(f"{service_name}_main", service_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {service_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    # Execute the module to populate it
    spec.loader.exec_module(module)

    # Get the FastAPI app
    if not hasattr(module, 'app'):
        raise AttributeError(f"Module {service_name} does not have an 'app' attribute")

    return module.app


def generate_openapi_spec(service_name: str, output_format: str = 'yaml') -> Dict[str, Any]:
    """Generate OpenAPI specification for a service.

    Args:
        service_name: Name of the service
        output_format: Output format ('yaml' or 'json')

    Returns:
        OpenAPI specification as a dictionary
    """
    print(f"Loading {service_name} service...")

    try:
        app = load_fastapi_app(service_name)
    except Exception as e:
        print(f"Error loading service: {e}")
        raise

    print(f"Generating OpenAPI spec for {service_name}...")

    # Get OpenAPI spec from FastAPI
    openapi_spec = app.openapi()

    # Add metadata about generation
    openapi_spec['info']['x-generated-by'] = 'generate_service_openapi.py'
    openapi_spec['info']['x-service-name'] = service_name
    openapi_spec['info']['description'] = (
        openapi_spec.get('info', {}).get('description', '') +
        f"\n\nThis specification is auto-generated from the {service_name} service FastAPI definition."
    )

    return openapi_spec


def save_spec(spec: Dict[str, Any], output_path: Path, output_format: str = 'yaml') -> None:
    """Save OpenAPI spec to file.

    Args:
        spec: OpenAPI specification dictionary
        output_path: Path to save the spec
        output_format: Output format ('yaml' or 'json')
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        if output_format == 'yaml':
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        else:
            json.dump(spec, f, indent=2)

    print(f"✓ Saved spec to: {output_path}")


def validate_spec(spec_path: Path) -> bool:
    """Validate OpenAPI specification.

    Args:
        spec_path: Path to the OpenAPI spec file

    Returns:
        True if valid, False otherwise
    """
    try:
        from openapi_spec_validator import validate_spec
        from openapi_spec_validator.readers import read_from_filename

        spec_dict, spec_url = read_from_filename(str(spec_path))
        validate_spec(spec_dict)
        print(f"✓ Validation passed: {spec_path}")
        return True
    except ImportError:
        print("Warning: openapi-spec-validator not installed, skipping validation")
        print("Install with: pip install openapi-spec-validator")
        return True
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate OpenAPI specifications for internal services',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate spec for reporting service
  ./generate_service_openapi.py --service reporting

  # Generate specs for all services
  ./generate_service_openapi.py --all

  # Generate and validate
  ./generate_service_openapi.py --service reporting --validate
        """
    )

    parser.add_argument(
        '--service',
        type=str,
        choices=['reporting', 'ingestion', 'auth', 'orchestrator'],
        help='Service name to generate spec for'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate specs for all services'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['yaml', 'json'],
        default='yaml',
        help='Output format (default: yaml)'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate generated specifications'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'openapi' / 'generated',
        help='Output directory for generated specs (default: openapi/generated)'
    )

    args = parser.parse_args()

    # Determine which services to process
    if args.all:
        services = ['reporting', 'ingestion', 'auth', 'orchestrator']
    elif args.service:
        services = [args.service]
    else:
        parser.error("Must specify either --service or --all")

    print(f"\n🔧 Service OpenAPI Generator")
    print(f"Output Directory: {args.output_dir}")
    print(f"Format: {args.format}")
    print(f"Services: {', '.join(services)}\n")

    # Generate specs for each service
    all_valid = True
    for service_name in services:
        try:
            print(f"\n{'='*60}")
            print(f"Processing: {service_name}")
            print(f"{'='*60}\n")

            # Generate spec
            spec = generate_openapi_spec(service_name, args.format)

            # Save spec
            output_file = args.output_dir / f"{service_name}.{args.format}"
            save_spec(spec, output_file, args.format)

            # Validate if requested
            if args.validate:
                if not validate_spec(output_file):
                    all_valid = False

            print(f"✅ Successfully generated spec for {service_name}\n")

        except Exception as e:
            print(f"❌ Failed to generate spec for {service_name}: {e}\n")
            all_valid = False

    # Summary
    print(f"\n{'='*60}")
    if all_valid:
        print("✨ All specifications generated successfully!")
        print(f"   Output directory: {args.output_dir}")
    else:
        print("⚠️  Some specifications failed to generate or validate")
        sys.exit(1)


if __name__ == '__main__':
    main()
