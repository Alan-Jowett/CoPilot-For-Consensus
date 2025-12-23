#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
ARM Template Validation Script

This script validates the Azure ARM template for syntax and structural correctness.
It does not perform Azure API validation but checks for:
- Valid JSON syntax
- Required template sections
- Parameter definitions
- Resource declarations
- Output definitions
"""

import json
import sys
from pathlib import Path


def validate_json_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate JSON syntax."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
        return True, "Valid JSON syntax"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_template_structure(file_path: Path) -> tuple[bool, list[str]]:
    """Validate ARM template structure."""
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        # Check required sections
        required_sections = ["$schema", "contentVersion", "resources"]
        for section in required_sections:
            if section not in template:
                errors.append(f"Missing required section: {section}")

        # Validate schema
        if "$schema" in template:
            expected_schema_prefix = "https://schema.management.azure.com/schemas/"
            if not template["$schema"].startswith(expected_schema_prefix):
                errors.append(f"Invalid schema URL: {template['$schema']}")

        # Validate contentVersion
        if "contentVersion" in template:
            if not isinstance(template["contentVersion"], str):
                errors.append("contentVersion must be a string")

        # Validate parameters section
        if "parameters" in template:
            params = template["parameters"]
            if not isinstance(params, dict):
                errors.append("parameters must be an object")
            else:
                for param_name, param_def in params.items():
                    if not isinstance(param_def, dict):
                        errors.append(f"Parameter '{param_name}' must be an object")
                    elif "type" not in param_def:
                        errors.append(f"Parameter '{param_name}' missing 'type' property")

        # Validate resources section
        if "resources" in template:
            resources = template["resources"]
            if not isinstance(resources, list):
                errors.append("resources must be an array")
            else:
                for i, resource in enumerate(resources):
                    if not isinstance(resource, dict):
                        errors.append(f"Resource at index {i} must be an object")
                    else:
                        required_resource_props = ["type", "apiVersion", "name"]
                        for prop in required_resource_props:
                            if prop not in resource:
                                errors.append(
                                    f"Resource at index {i} missing required property: {prop}"
                                )

        # Validate outputs section (if present)
        if "outputs" in template:
            outputs = template["outputs"]
            if not isinstance(outputs, dict):
                errors.append("outputs must be an object")
            else:
                for output_name, output_def in outputs.items():
                    if not isinstance(output_def, dict):
                        errors.append(f"Output '{output_name}' must be an object")
                    elif "type" not in output_def:
                        errors.append(f"Output '{output_name}' missing 'type' property")
                    elif "value" not in output_def:
                        errors.append(f"Output '{output_name}' missing 'value' property")

        return len(errors) == 0, errors

    except Exception as e:
        return False, [f"Error validating template structure: {e}"]


def validate_parameters_file(file_path: Path) -> tuple[bool, list[str]]:
    """Validate ARM parameters file."""
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            params_file = json.load(f)

        # Check required sections
        if "$schema" not in params_file:
            errors.append("Missing required section: $schema")

        if "contentVersion" not in params_file:
            errors.append("Missing required section: contentVersion")

        if "parameters" not in params_file:
            errors.append("Missing required section: parameters")
        else:
            params = params_file["parameters"]
            if not isinstance(params, dict):
                errors.append("parameters must be an object")
            else:
                for param_name, param_value in params.items():
                    if not isinstance(param_value, dict):
                        errors.append(f"Parameter '{param_name}' must be an object")
                    elif "value" not in param_value and "reference" not in param_value:
                        errors.append(
                            f"Parameter '{param_name}' must have either 'value' or 'reference'"
                        )

        return len(errors) == 0, errors

    except Exception as e:
        return False, [f"Error validating parameters file: {e}"]


def main():
    """Main validation function."""
    script_dir = Path(__file__).parent
    template_file = script_dir / "azuredeploy.json"
    parameters_file = script_dir / "azuredeploy.parameters.json"

    print("ARM Template Validation")
    print("=" * 60)

    all_valid = True

    # Validate template JSON syntax
    print(f"\nValidating template file: {template_file}")
    valid, message = validate_json_syntax(template_file)
    print(f"  JSON Syntax: {'✓ PASS' if valid else '✗ FAIL'} - {message}")
    all_valid = all_valid and valid

    # Validate template structure
    if valid:
        valid, errors = validate_template_structure(template_file)
        if valid:
            print("  Template Structure: ✓ PASS")
        else:
            print("  Template Structure: ✗ FAIL")
            for error in errors:
                print(f"    - {error}")
            all_valid = False

    # Validate parameters file JSON syntax
    print(f"\nValidating parameters file: {parameters_file}")
    valid, message = validate_json_syntax(parameters_file)
    print(f"  JSON Syntax: {'✓ PASS' if valid else '✗ FAIL'} - {message}")
    all_valid = all_valid and valid

    # Validate parameters file structure
    if valid:
        valid, errors = validate_parameters_file(parameters_file)
        if valid:
            print("  Parameters Structure: ✓ PASS")
        else:
            print("  Parameters Structure: ✗ FAIL")
            for error in errors:
                print(f"    - {error}")
            all_valid = False

    # Summary
    print("\n" + "=" * 60)
    if all_valid:
        print("✓ All validations passed!")
        return 0
    else:
        print("✗ Validation failed. Please fix the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
