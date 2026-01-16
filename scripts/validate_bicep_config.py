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


def _is_bicep_conditional(value: object) -> bool:
    if value is None:
        return False
    text = str(value)
    return "?" in text


def _validate_schema_discriminant(env_vars: dict, schema: dict, context: str) -> list[str]:
    """Validate a schema-level discriminant (if present).

    Some driver schemas have a root-level 'discriminant' (not inside 'properties').
    Example: archive_azureblob.json requires AZUREBLOB_AUTH_TYPE.
    """

    issues: list[str] = []
    discriminant = schema.get("discriminant")
    if not isinstance(discriminant, dict):
        return issues

    if discriminant.get("source") != "env":
        return issues

    env_var = discriminant.get("env_var")
    if not isinstance(env_var, str) or not env_var:
        return issues

    required = bool(discriminant.get("required", False))
    enum_values = discriminant.get("enum", [])

    if env_var not in env_vars:
        if required:
            issues.append(f"Missing REQUIRED discriminant: {env_var} ({context})")
        else:
            issues.append(f"Missing discriminant: {env_var} ({context})")
        return issues

    value = env_vars.get(env_var)
    if value is None or _is_bicep_conditional(value):
        # Can't evaluate; skip enum validation.
        return issues

    if isinstance(enum_values, list) and enum_values and value not in enum_values:
        issues.append(f"Invalid discriminant value for {env_var}: '{value}' not in {enum_values} ({context})")

    return issues


def _select_oneof_variant_by_discriminant(env_vars: dict, schema: dict) -> dict:
    """Best-effort selection of a oneOf variant using schema.discriminant.

    Returns the selected variant schema, or the original schema if no selection is possible.
    """

    one_of = schema.get("oneOf")
    if not isinstance(one_of, list) or not one_of:
        return schema

    discriminant = schema.get("discriminant")
    if not isinstance(discriminant, dict):
        return schema

    env_var = discriminant.get("env_var")
    field = discriminant.get("field")
    if not isinstance(env_var, str) or not env_var:
        return schema
    if not isinstance(field, str) or not field:
        return schema

    value = env_vars.get(env_var)
    if value is None or _is_bicep_conditional(value):
        return schema

    for variant in one_of:
        if not isinstance(variant, dict):
            continue
        props = variant.get("properties")
        if not isinstance(props, dict):
            continue
        field_spec = props.get(field)
        if not isinstance(field_spec, dict):
            continue
        const_value = field_spec.get("const")
        if const_value == value:
            return variant

    return schema


def _normalize_secret_name_for_key_vault(schema_secret_name: str) -> str:
    """Convert schema secret_name to Azure Key Vault secret resource name.

    Convention: schema uses snake_case; Key Vault secret names use hyphens.
    """

    return schema_secret_name.replace("_", "-")


def _extract_keyvault_created_secret_names(bicep_content: str, vault_name_var: str) -> set[str]:
    """Extract KV secret names created in a given vault variable context.

    This is a best-effort helper that recognizes a small set of common
    Bicep patterns. Supported single-line forms include:

      name: '${keyVaultName}/jwt-private-key'
      name: "${keyVaultName}/jwt-private-key"
      name: concat(keyVaultName, '/jwt-private-key')

    More complex or multi-line expressions (for example, `name` built across
    multiple `concat` calls or interpolations) are intentionally ignored.
    """

    secret_names: set[str] = set()

    # 1) Interpolated string: name: "${<vaultVar>/secret-name}"
    # Matches: name: '${keyVaultName}/jwt-private-key' and name: "${keyVaultName}/jwt-private-key"
    pattern_interpolated = rf"name:\s*['\"]\$\{{{re.escape(vault_name_var)}\}}/([^'\"]+)['\"]"
    for match in re.finditer(pattern_interpolated, bicep_content):
        secret_names.add(match.group(1))

    # 2) concat() form: name: concat(<vaultVar>, '/secret-name')
    # We capture the portion after the leading slash in the literal.
    # Matches: name: concat(keyVaultName, '/jwt-private-key')
    pattern_concat = rf"name:\s*concat\(\s*{re.escape(vault_name_var)}\s*,\s*['\"]/+([^'\"/]+)['\"]\s*\)"
    for match in re.finditer(pattern_concat, bicep_content):
        secret_names.add(match.group(1))

    return secret_names


def _load_iac_keyvault_secret_inventory() -> dict[str, set[str]]:
    """Load a best-effort inventory of Key Vault secrets created by IaC.

    Returns:
      {
        'env': {<secret-names>},
        'core': {<secret-names>},
      }
    """

    repo_root = Path(__file__).parent.parent
    env_main = repo_root / "infra" / "azure" / "main.bicep"
    core_main = repo_root / "infra" / "azure" / "core.bicep"

    inventory: dict[str, set[str]] = {"env": set(), "core": set()}

    if env_main.exists():
        content = env_main.read_text(encoding="utf-8")
        inventory["env"] = _extract_keyvault_created_secret_names(content, "keyVaultName")

    if core_main.exists():
        content = core_main.read_text(encoding="utf-8")
        inventory["core"] = _extract_keyvault_created_secret_names(content, "coreKeyVaultName")

    return inventory


def _kv_scope_from_env(env_vars: dict) -> str:
    """Return which KV scope the service is configured to use.

    This is a heuristic used for static validation.
    - In Container Apps module, AZURE_KEY_VAULT_NAME is usually set to the env param 'keyVaultName'.
    """

    name = env_vars.get("AZURE_KEY_VAULT_NAME")
    if not name:
        return "unknown"

    # Common patterns in the Bicep module (static, not evaluated).
    if str(name).strip() == "keyVaultName":
        return "env"
    if str(name).strip() == "coreKeyVaultName":
        return "core"

    return "unknown"


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
    # More robust pattern that handles values on the same line or next line
    # Pattern: name: 'NAME' followed by value: on same or next line
    pattern = r"name:\s*['\"]([^'\"]+)['\"]\s*\n?\s*value:\s*(.+?)(?=\n\s*\})"
    
    for match in re.finditer(pattern, env_content, re.DOTALL | re.MULTILINE):
        name = match.group(1)
        value = match.group(2).strip()
        
        # Remove trailing comma if present
        value = value.rstrip(",").strip()
        
        # Remove surrounding quotes if present
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        elif value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        
        # Store the full value for validation (even if conditional)
        env_vars[name] = value
    
    return env_vars


def load_schema(service_name: str) -> dict:
    """Load the service schema from docs/schemas/configs/services/{service_name}.json"""
    schema_path = Path(__file__).parent.parent / "docs" / "schemas" / "configs" / "services" / f"{service_name}.json"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_ref(ref_path: str, base_path: Path) -> dict:
    """
    Resolve a $ref pointer and load the referenced schema.
    
    Args:
        ref_path: The $ref path (e.g., "../adapters/metrics.json")
        base_path: Base path to resolve relative references from
    
    Returns:
        The loaded schema dict
    """
    # Resolve relative path from base
    resolved_path = (base_path / ref_path).resolve()
    
    if not resolved_path.exists():
        raise FileNotFoundError(f"Referenced schema not found: {resolved_path} (from {ref_path})")
    
    with open(resolved_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _extract_keyvault_references_from_env(env_vars: dict) -> dict[str, str]:
    """
    Scan env var values for Key Vault secret references.
    Returns dict mapping env var name to 'KEY_VAULT_REF' marker.
    
    These should NOT exist - secrets should be loaded via secret provider, not env vars.
    """
    keyvault_refs: dict[str, str] = {}

    for env_name, value in env_vars.items():
        if not value:
            continue
        # Look for @Microsoft.KeyVault( pattern (even with Bicep variable interpolation)
        if "@Microsoft.KeyVault(" in str(value):
            keyvault_refs[env_name] = "KEY_VAULT_REF"

    return keyvault_refs


def validate_config(env_vars: dict, schema: dict, service_name: str) -> list:
    """
    Validate environment variables against schema.
    
    Returns list of issues found (empty if valid).
    """
    issues = []
    required_secrets: set[str] = set()
    
    # Get service settings from schema
    service_settings = schema.get("service_settings", {})
    
    # Validate service settings (old validation logic - kept for completeness)
    for setting_name, setting_config in service_settings.items():
        if not isinstance(setting_config, dict):
            continue
        
        # Get discriminant info (if any)
        discriminant = setting_config.get("discriminant")
        if discriminant:
            discriminant_env_var = discriminant.get("env_var")
            enum_values = discriminant.get("enum", [])
            
            if discriminant_env_var:
                # Check discriminant env var exists and has valid value
                if discriminant_env_var not in env_vars:
                    issues.append(f"Missing discriminant environment variable: {discriminant_env_var} (required for setting '{setting_name}')")
                elif env_vars[discriminant_env_var] is not None:
                    value = env_vars[discriminant_env_var]
                    if value not in enum_values:
                        issues.append(f"Invalid discriminant value for {discriminant_env_var}: '{value}' not in {enum_values}")
    
    # Check for Key Vault references in env vars (these should NOT exist)
    keyvault_refs = _extract_keyvault_references_from_env(env_vars)
    if keyvault_refs:
        issues.append(
            f"INVALID: Environment variables contain Key Vault secret references. "
            f"Secrets should be loaded via secret_provider, not injected as env vars. "
            f"Remove these env vars: {list(keyvault_refs.keys())}"
        )
    
    # Validate adapter discriminants and driver requirements (including secrets)
    adapters = schema.get("adapters", {})
    schema_base_path = Path(__file__).parent.parent / "docs" / "schemas" / "configs" / "services"
    
    for adapter_name, adapter_ref in adapters.items():
        if not isinstance(adapter_ref, dict) or "$ref" not in adapter_ref:
            continue
        
        try:
            # Resolve and load the adapter schema (keep its path to resolve driver refs)
            adapter_schema_path = (schema_base_path / adapter_ref["$ref"]).resolve()
            if not adapter_schema_path.exists():
                raise FileNotFoundError(f"Referenced schema not found: {adapter_schema_path} (from {adapter_ref['$ref']})")
            with open(adapter_schema_path, "r", encoding="utf-8") as f:
                adapter_schema = json.load(f)
            adapter_schema_dir = adapter_schema_path.parent
            
            # Check for discriminant in the adapter schema
            discriminant = adapter_schema.get("properties", {}).get("discriminant")
            if not discriminant:
                continue
            
            discriminant_env_var = discriminant.get("env_var")
            enum_values = discriminant.get("enum", [])
            required = discriminant.get("required", False)
            
            if not discriminant_env_var:
                continue
            
            # Check if the discriminant env var exists
            if discriminant_env_var not in env_vars:
                if required:
                    issues.append(f"Missing REQUIRED adapter discriminant: {discriminant_env_var} (adapter '{adapter_name}')")
                else:
                    issues.append(f"Missing adapter discriminant: {discriminant_env_var} (adapter '{adapter_name}')")
                continue

            selected_driver = env_vars[discriminant_env_var]
            if selected_driver is None:
                # Conditional or computed; skip deep validation for this adapter
                continue
            
            # Check if value contains ternary operator (Bicep conditional expression)
            # These can't be evaluated at validation time, so skip deep validation
            if '?' in str(selected_driver):
                # Still validate it's a valid Bicep ternary pattern (has ? and :)
                if ':' not in str(selected_driver):
                    issues.append(
                        f"Invalid ternary expression for {discriminant_env_var}: missing ':' (adapter '{adapter_name}')"
                    )
                # Skip deep validation since we can't determine which driver will be selected at runtime
                continue

            if enum_values and selected_driver not in enum_values:
                issues.append(
                    f"Invalid discriminant value for {discriminant_env_var}: '{selected_driver}' not in {enum_values} (adapter '{adapter_name}')"
                )
                continue

            # Deep-validate the selected driver schema for required env/secret fields
            drivers_data = adapter_schema.get("properties", {}).get("drivers", {}).get("properties", {})
            driver_info = drivers_data.get(selected_driver)
            if not driver_info:
                issues.append(
                    f"Driver '{selected_driver}' not defined in adapter schema for '{adapter_name}'"
                )
                continue

            driver_ref = driver_info.get("$ref")
            if not driver_ref:
                continue

            driver_schema_path = (adapter_schema_dir / driver_ref).resolve()
            if not driver_schema_path.exists():
                issues.append(
                    f"Referenced driver schema not found: {driver_schema_path} (adapter '{adapter_name}', driver '{selected_driver}')"
                )
                continue

            with open(driver_schema_path, "r", encoding="utf-8") as f:
                driver_schema = json.load(f)

            # Some driver schemas use a root-level discriminant + oneOf variants.
            # Validate that discriminant env var is present (if required), then
            # select a variant (if possible) so we can validate required env vars.
            issues.extend(
                _validate_schema_discriminant(
                    env_vars,
                    driver_schema,
                    context=f"adapter '{adapter_name}' driver '{selected_driver}'",
                )
            )
            effective_driver_schema = _select_oneof_variant_by_discriminant(env_vars, driver_schema)
            driver_props = effective_driver_schema.get("properties", {})

            # Support schemas that express "at least one of" requirements.
            # Example: Azure Key Vault secret provider driver needs one of
            # AZURE_KEY_VAULT_URI or AZURE_KEY_VAULT_NAME.
            # Combine parent-level and variant-level one-of requirements (if any).
            required_one_of: list = []
            parent_required_one_of = driver_schema.get("x-required_one_of")
            if isinstance(parent_required_one_of, list):
                required_one_of.extend(parent_required_one_of)
            variant_required_one_of = effective_driver_schema.get("x-required_one_of")
            if isinstance(variant_required_one_of, list):
                required_one_of.extend(variant_required_one_of)
            if isinstance(required_one_of, list):
                for group in required_one_of:
                    if not isinstance(group, list) or not group:
                        continue

                    satisfied = False
                    required_env_vars: list[str] = []

                    for prop_name in group:
                        if prop_name not in driver_props:
                            continue
                        prop_spec = driver_props.get(prop_name)
                        if not isinstance(prop_spec, dict):
                            continue
                        if prop_spec.get("source") != "env":
                            continue

                        env_var = prop_spec.get("env_var")
                        if isinstance(env_var, str) and env_var:
                            required_env_vars.append(env_var)
                            if env_var in env_vars and env_vars[env_var] not in (None, ""):
                                satisfied = True

                    if required_env_vars and not satisfied:
                        issues.append(
                            f"Missing REQUIRED one-of env vars {required_env_vars} for adapter '{adapter_name}' "
                            f"driver '{selected_driver}'"
                        )
            for prop_name, prop_spec in driver_props.items():
                if not isinstance(prop_spec, dict):
                    continue

                source = prop_spec.get("source")
                required_prop = prop_spec.get("required", False)

                if source == "env":
                    env_var = prop_spec.get("env_var")
                    if env_var and required_prop and env_var not in env_vars:
                        issues.append(
                            f"Missing REQUIRED env var '{env_var}' for adapter '{adapter_name}' driver '{selected_driver}' (property '{prop_name}')"
                        )
                elif source == "secret":
                    # Secrets should be loaded via secret_provider, not via env vars
                    # Check if any env var references this secret (which is wrong)
                    secret_name = prop_spec.get("secret_name")
                    required_prop = prop_spec.get("required", False)
                    if secret_name:
                        secret_candidates = secret_name if isinstance(secret_name, list) else [secret_name]

                        # Track required secrets for IaC coverage validation
                        if required_prop:
                            for candidate in secret_candidates:
                                if isinstance(candidate, str) and candidate:
                                    required_secrets.add(candidate)

                        # Check if any env var has a KeyVault reference to this secret
                        for env_var_name, referenced_secret in keyvault_refs.items():
                            if referenced_secret in secret_candidates:
                                issues.append(
                                    f"INVALID: Env var '{env_var_name}' contains Key Vault reference to secret '{referenced_secret}' "
                                    f"but adapter '{adapter_name}' driver '{selected_driver}' defines this as source='secret'. "
                                    f"Remove the env var - secrets should be loaded via secret_provider, not injected as env vars."
                                )
        
        except FileNotFoundError as e:
            issues.append(f"Could not resolve adapter schema for '{adapter_name}': {e}")
        except Exception as e:
            issues.append(f"Error validating adapter '{adapter_name}': {e}")
    
    issues.extend(_validate_required_secrets_created_by_iac(env_vars, required_secrets))
    return issues


def _validate_required_secrets_created_by_iac(env_vars: dict, required_secrets: set[str]) -> list[str]:
    """Static check: required schema secrets must be created by IaC in the selected Key Vault."""

    issues: list[str] = []

    if not required_secrets:
        return issues

    if env_vars.get("SECRET_PROVIDER_TYPE") != "azure_key_vault":
        return issues

    kv_scope = _kv_scope_from_env(env_vars)
    if kv_scope == "unknown":
        # Can't confidently map to env/core based on static values.
        return issues

    inventory = _load_iac_keyvault_secret_inventory()
    created = inventory.get(kv_scope, set())

    # Some secrets are documented as out-of-band/manual (OAuth). Don't enforce these.
    manual_prefixes = (
        "github_oauth_",
        "google_oauth_",
        "microsoft_oauth_",
        "entra_oauth_",
    )

    for schema_secret in sorted(required_secrets):
        if schema_secret.startswith(manual_prefixes):
            continue

        kv_secret = _normalize_secret_name_for_key_vault(schema_secret)
        if kv_secret not in created:
            issues.append(
                f"Missing REQUIRED secret '{kv_secret}' in {kv_scope} Key Vault IaC. "
                "Update your infrastructure-as-code (for example, the Key Vault secret resources in "
                "infra/azure/main.bicep or infra/azure/core.bicep) to create this secret before deployment."
            )

    return issues


def main():
    if len(sys.argv) < 3:
        print("Usage: python validate_bicep_config.py <bicep_file> <service_name> [--verbose]")
        print("Example: python validate_bicep_config.py infra/azure/modules/containerapps.bicep auth")
        print("         python validate_bicep_config.py infra/azure/modules/containerapps.bicep auth --verbose")
        sys.exit(1)
    
    bicep_file = sys.argv[1]
    service_name = sys.argv[2]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
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
        
        if verbose:
            print("\n   Environment variables found:")
            for name in sorted(env_vars.keys()):
                value = env_vars[name]
                if value is None:
                    print(f"     {name} = <conditional/computed>")
                else:
                    # Truncate long values for display
                    display_val = value if len(str(value)) <= 50 else str(value)[:50] + "..."
                    print(f"     {name} = {display_val}")
        
        # Load schema
        print(f"📖 Loading schema for '{service_name}'...")
        schema = load_schema(service_name)
        
        if verbose:
            print(f"   Schema adapters required: {list(schema.get('adapters', {}).keys())}")
        
        # Validate
        print(f"✓ Validating configuration against schema...")
        issues = validate_config(env_vars, schema, service_name)
        
        if issues:
            print(f"\n❌ Configuration validation failed ({len(issues)} issues):\n")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            
            if verbose:
                print("\n📊 Validation Context:")
                print(f"   Service: {service_name}")
                print(f"   Total env vars: {len(env_vars)}")
                print(f"   Missing/invalid env vars:")
                for issue in issues:
                    if "Missing" in issue or "Invalid" in issue:
                        # Extract env var name from issue
                        parts = issue.split("'")
                        if len(parts) >= 2:
                            print(f"     - {parts[1]}")
            
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
