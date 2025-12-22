# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Configuration discovery endpoint support for microservices."""

import json
import os
from typing import Any, Dict, Optional

from .schema_loader import ConfigSchema, _resolve_schema_directory


def get_configuration_schema_response(
    service_name: str,
    schema_dir: Optional[str] = None,
    service_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Get configuration schema response for discovery endpoint.
    
    This function loads the configuration schema and returns a dictionary
    containing the schema, version information, and service metadata.
    
    Args:
        service_name: Name of the service
        schema_dir: Directory containing schema files (defaults to standard locations)
        service_version: Current service version (defaults to SERVICE_VERSION env var)
        
    Returns:
        Dictionary containing schema and version information
        
    Raises:
        FileNotFoundError: If schema file is not found
        
    Example response:
        {
            "service_name": "parsing",
            "service_version": "0.1.0",
            "schema_version": "1.0.0",
            "min_service_version": "0.1.0",
            "schema": { ... full JSON schema ... }
        }
    """
    # Determine schema directory
    schema_dir = _resolve_schema_directory(schema_dir)
    
    # Load schema file
    schema_path = os.path.join(schema_dir, f"{service_name}.json")
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    # Read the raw schema file
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)
    
    # Parse schema for version info
    schema = ConfigSchema.from_dict(schema_data)
    
    # Get service version
    if service_version is None:
        service_version = os.environ.get("SERVICE_VERSION", "0.0.0")
    
    # Build response
    response = {
        "service_name": schema.service_name,
        "service_version": service_version,
        "schema_version": schema.schema_version,
        "min_service_version": schema.min_service_version,
        "schema": schema_data,
    }
    
    return response
