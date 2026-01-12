# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Validate Bicep Container Apps configuration against service schemas.

This script extracts environment variables from a Bicep file and validates
them against the corresponding service schema to catch configuration errors
before deployment.

Usage:
    python validate_bicep_config.py <bicep_file> <service_name>
    python validate_bicep_config.py infra/azure/modules/containerapps.bicep auth
"""

import json
import re
import sys
from pathlib import Path


def extract_env_vars(bicep_content: str, service_name: str) -> dict:
    """
    Extract environment variables for a service from Bicep file content.
    
    Looks for patterns like:
    resource authApp 'Microsoft.App/containerApps@2024-03-01' = {
        ...
        env: [
            { name: 'VAR_NAME', value: 'value' }
            ...
        ]
    }
    
    Returns dict mapping env var names to values (or None for conditionals).
    """
    env_vars = {}
    
    # Find the service resource block - support various naming patterns
    # Look for "resource <name> 'Microsoft.App/containerApps" where name contains the service
    service_patterns = [
        rf"resource\s+\w*{service_name}\w*\s+'Microsoft\.App/containerApps",
    ]
    
    resource_start = -1
    for pattern in service_patterns:
        match = re.search(pattern, bicep_content, re.IGNORECASE)
        if match:
            resource_start = match.start()
            break
    
    if resource_start == -1:
        raise ValueError(f"Could not find resource block for service '{service_name}'. Pattern: resource <name> 'Microsoft.App/containerApps'")
    
    # Find the containers array and then the env array within it
    # Look from resource_start for "env: ["
    env_start = bicep_content.find("env: [", resource_start)
    if env_start == -1:
        raise ValueError(f"Could not find 'env: [' array for service '{service_name}' after position {resource_start}")
    
    # Find the closing ] of the env array - need to track nesting
    bracket_count = 1  # We're starting after "env: ["
    i = env_start + 6  # Start after "env: ["
    env_end = -1
    in_string = False
    string_char = None
    
    while i < len(bicep_content) and bracket_count > 0:
        char = bicep_content[i]
        
        # Handle string literals
        if char in ('"', "'") and (i == 0 or bicep_content[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        
        # Only count brackets outside strings
        if not in_string:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    env_end = i
                    break
        
        i += 1
    
    if env_end == -1:
        raise ValueError(f"Could not find closing bracket for 'env:' array for service '{service_name}'")
    
    env_content = bicep_content[env_start + 6:env_end]
    
    # Extract name-value pairs
    # More robust pattern that handles various spacing and indentation
    # Pattern: name: 'NAME', value: 'value'  or name: 'NAME' value: '...'
    pattern = r"name:\s*['\"]([^'\"]+)['\"]\s*(?:,\s*)?value:\s*([^}\n]*)(?=\n\s*\})"
    
    for match in re.finditer(pattern, env_content, re.MULTILINE):
        name = match.group(1)
        value = match.group(2).strip()
        
        # Remove trailing comma if present
        value = value.rstrip(",").strip()
        
        # Simplify value: remove quotes, handle ternary operators
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        elif value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        
        # For ternary or complex expressions, just mark as conditional
        if "?" in value or "@" in value or "resourceId" in value or value.startswith("list") or value.startswith("parameters"):
            env_vars[name] = None  # Mark as conditional/computed
        else:
            env_vars[name] = value
    
    return env_vars


def load_schema(service_name: str) -> dict:
    """Load the service schema from docs/schemas/configs/services/{service_name}.json"""
    schema_path = Path(__file__).parent.parent / "docs" / "schemas" / "configs" / "services" / f"{service_name}.json"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    
    with open(schema_path, 'r') as f:
        return json.load(f)


def validate_config(env_vars: dict, schema: dict) -> list:
    """
    Validate environment variables against schema.
    
    Returns list of issues found (empty if valid).
    """
    issues = []
    
    # Get service settings from schema
    service_settings = schema.get("service_settings", {})
    
    # Track which fields we've validated
    validated_fields = set()
    
    # Validate each adapter configuration
    for adapter_name, adapter_config in service_settings.items():
        if not isinstance(adapter_config, dict):
            continue
        
        # Get discriminant info
        discriminant = adapter_config.get("discriminant")
        if not discriminant:
            continue
        
        discriminant_field = discriminant.get("field")
        discriminant_env_var = discriminant.get("env_var")
        enum_values = discriminant.get("enum", [])
        
        if not discriminant_env_var:
            continue
        
        # Check discriminant env var exists and has valid value
        if discriminant_env_var not in env_vars:
            issues.append(f"Missing discriminant environment variable: {discriminant_env_var} (required for adapter '{adapter_name}')")
        elif env_vars[discriminant_env_var] is not None:
            value = env_vars[discriminant_env_var]
            if value not in enum_values:
                issues.append(f"Invalid discriminant value for {discriminant_env_var}: '{value}' not in {enum_values}")
        
        # Get properties for this adapter
        properties = adapter_config.get("properties", {})
        
        # Check required properties
        required = adapter_config.get("required", [])
        for field_name in required:
            if field_name not in properties:
                continue
            
            prop = properties[field_name]
            env_var = prop.get("env_var")
            
            if env_var:
                validated_fields.add(env_var)
                if env_var not in env_vars:
                    issues.append(f"Missing required field: {env_var} (required by adapter '{adapter_name}', field '{field_name}')")
                elif env_vars[env_var] is None:
                    issues.append(f"Required field has conditional value: {env_var} (adapter '{adapter_name}', field '{field_name}')")
        
        # Check optional properties and validate their env vars exist
        for field_name, prop in properties.items():
            if field_name in required:
                continue
            
            env_var = prop.get("env_var")
            if env_var:
                validated_fields.add(env_var)
    
    # Check for env vars that don't map to any schema field (might be obsolete or typos)
    # This is a warning, not an error
    schema_env_vars = set()
    for adapter_name, adapter_config in service_settings.items():
        if isinstance(adapter_config, dict):
            disc = adapter_config.get("discriminant", {})
            if disc.get("env_var"):
                schema_env_vars.add(disc.get("env_var"))
            
            props = adapter_config.get("properties", {})
            for prop in props.values():
                if isinstance(prop, dict) and prop.get("env_var"):
                    schema_env_vars.add(prop.get("env_var"))
    
    for env_var in env_vars:
        if env_var not in schema_env_vars and not env_var.startswith("SERVICE_"):
            # Ignore SERVICE_VERSION and similar top-level vars
            pass
    
    return issues


def main():
    if len(sys.argv) < 3:
        print("Usage: python validate_bicep_config.py <bicep_file> <service_name>")
        print("Example: python validate_bicep_config.py infra/azure/modules/containerapps.bicep auth")
        sys.exit(1)
    
    bicep_file = sys.argv[1]
    service_name = sys.argv[2]
    
    try:
        # Read bicep file
        bicep_path = Path(bicep_file)
        if not bicep_path.exists():
            print(f"❌ Bicep file not found: {bicep_file}", file=sys.stderr)
            sys.exit(1)
        
        with open(bicep_path, 'r') as f:
            bicep_content = f.read()
        
        # Extract env vars from Bicep
        print(f"📋 Extracting environment variables for '{service_name}' from Bicep...")
        env_vars = extract_env_vars(bicep_content, service_name)
        print(f"   Found {len(env_vars)} environment variables")
        
        # Load schema
        print(f"📖 Loading schema for '{service_name}'...")
        schema = load_schema(service_name)
        
        # Validate
        print(f"✓ Validating configuration against schema...")
        issues = validate_config(env_vars, schema)
        
        if issues:
            print(f"\n❌ Configuration validation failed ({len(issues)} issues):\n")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            sys.exit(1)
        else:
            print(f"\n✅ Configuration is valid for service '{service_name}'")
            sys.exit(0)
    
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
