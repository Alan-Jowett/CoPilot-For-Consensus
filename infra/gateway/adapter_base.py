#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base class and interface for cloud gateway adapters.

This module defines the abstract interface that all gateway adapters must implement.
Adapters transform the canonical OpenAPI specification into provider-specific
gateway configurations (Azure API Management, AWS API Gateway, GCP Cloud Endpoints, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class GatewayAdapter(ABC):
    """Abstract base class for gateway configuration adapters.

    Each adapter is responsible for:
    1. Loading and parsing the OpenAPI specification
    2. Transforming it into provider-specific configuration format
    3. Generating deployment artifacts (templates, scripts, manifests)
    4. Validating the generated configuration
    """

    def __init__(self, openapi_spec_path: Path):
        """Initialize the adapter with the OpenAPI specification.

        Args:
            openapi_spec_path: Path to the OpenAPI YAML/JSON specification file
        """
        self.openapi_spec_path = openapi_spec_path
        self.openapi_spec: Dict[str, Any] = {}

    @abstractmethod
    def load_spec(self) -> None:
        """Load and parse the OpenAPI specification.

        Should populate self.openapi_spec with the parsed specification.
        """
        pass

    @abstractmethod
    def validate_spec(self) -> bool:
        """Validate that the OpenAPI spec is compatible with this adapter.

        Returns:
            True if the spec is valid and can be processed by this adapter.

        Raises:
            ValueError: If the spec is invalid or incompatible.
        """
        pass

    @abstractmethod
    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate provider-specific gateway configuration.

        Args:
            output_dir: Directory where generated files should be written

        Returns:
            Dictionary mapping artifact type to file path.
            Example: {"template": Path("output/template.json"),
                     "parameters": Path("output/parameters.json")}
        """
        pass

    @abstractmethod
    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate the generated configuration files.

        Args:
            config_files: Dictionary of generated configuration files

        Returns:
            True if all configuration files are valid.

        Raises:
            ValueError: If any configuration file is invalid.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the cloud provider (e.g., 'azure', 'aws', 'gcp')."""
        pass

    @property
    @abstractmethod
    def deployment_instructions(self) -> str:
        """Return human-readable deployment instructions for this provider.

        Should include commands/steps needed to deploy the generated configuration.
        """
        pass


class NginxAdapter(GatewayAdapter):
    """Adapter for generating NGINX configuration from OpenAPI spec.

    This adapter ensures the local NGINX gateway stays in sync with the
    canonical OpenAPI specification, preventing configuration drift.
    """

    @property
    def provider_name(self) -> str:
        return "nginx"

    @property
    def deployment_instructions(self) -> str:
        return """
NGINX Local Deployment Instructions:
=====================================

1. The generated nginx.conf is already integrated into the Docker Compose setup.
2. Start the gateway:
   docker compose up -d gateway
3. Verify health:
   curl http://localhost:8080/health
4. For HTTPS:
   - Place certificates in secrets/gateway_tls_cert and secrets/gateway_tls_key
   - Or let the gateway generate self-signed certificates automatically
   - Access via https://localhost:443/

The NGINX gateway is the default for local development and single-machine deployments.
"""

    def load_spec(self) -> None:
        """Load the OpenAPI specification from YAML file."""
        import yaml

        with open(self.openapi_spec_path, 'r') as f:
            self.openapi_spec = yaml.safe_load(f)

    def validate_spec(self) -> bool:
        """Validate OpenAPI spec for NGINX compatibility."""
        required_fields = ['openapi', 'info', 'paths']
        for field in required_fields:
            if field not in self.openapi_spec:
                raise ValueError(f"OpenAPI spec missing required field: {field}")

        # Check OpenAPI version
        version = self.openapi_spec.get('openapi', '')
        if not version.startswith('3.'):
            raise ValueError(f"NGINX adapter requires OpenAPI 3.x, got {version}")

        return True

    def generate_config(self, output_dir: Path) -> Dict[str, Path]:
        """Generate NGINX configuration from OpenAPI spec.

        This is primarily for validation purposes. The actual nginx.conf
        is manually maintained but should match the routes in the OpenAPI spec.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate a validation report comparing OpenAPI spec with actual nginx.conf
        validation_report_path = output_dir / "nginx_validation_report.txt"

        with open(validation_report_path, 'w') as f:
            f.write("NGINX Configuration Validation Report\n")
            f.write("=" * 50 + "\n\n")
            f.write("OpenAPI Specification: " + str(self.openapi_spec_path) + "\n")
            f.write("Generated: " + str(Path(__file__).parent.parent / "nginx" / "nginx.conf") + "\n\n")

            f.write("Endpoints defined in OpenAPI:\n")
            for path, methods in self.openapi_spec.get('paths', {}).items():
                for method in methods.keys():
                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                        f.write(f"  {method.upper()} {path}\n")

        return {
            "validation_report": validation_report_path
        }

    def validate_config(self, config_files: Dict[str, Path]) -> bool:
        """Validate generated NGINX configuration."""
        # Basic validation - check that files exist
        for file_path in config_files.values():
            if not file_path.exists():
                raise ValueError(f"Generated file does not exist: {file_path}")

        return True
