# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema compatibility checker for configuration evolution."""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from .schema_loader import _parse_semver


class CompatibilityIssue:
    """Represents a compatibility issue between schemas."""
    
    BREAKING = "BREAKING"
    WARNING = "WARNING"
    INFO = "INFO"
    
    def __init__(self, severity: str, message: str, field: Optional[str] = None):
        self.severity = severity
        self.message = message
        self.field = field
    
    def __str__(self):
        if self.field:
            return f"[{self.severity}] {self.field}: {self.message}"
        return f"[{self.severity}] {self.message}"


def check_schema_compatibility(
    old_schema: Dict[str, Any],
    new_schema: Dict[str, Any],
) -> List[CompatibilityIssue]:
    """Check compatibility between two configuration schemas.
    
    Args:
        old_schema: Previous schema version
        new_schema: New schema version
        
    Returns:
        List of compatibility issues found
        
    Breaking changes:
        - Field removal
        - Type change
        - Making optional field required
        - Default value change for required fields
        
    Warnings:
        - Deprecated fields
        - Default value changes for optional fields
    """
    issues = []
    
    # Check version changes
    old_version = old_schema.get("schema_version")
    new_version = new_schema.get("schema_version")
    
    if old_version and new_version:
        try:
            old_parts = _parse_semver(old_version)
            new_parts = _parse_semver(new_version)
        except ValueError:
            # Invalid version format, skip comparison
            old_parts = new_parts = (0, 0, 0)
        
        if old_parts > new_parts:
            issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                f"Schema version downgrade: {old_version} -> {new_version}"
            ))
    
    # Get field sets
    old_fields = old_schema.get("fields", {})
    new_fields = new_schema.get("fields", {})
    
    old_field_names = set(old_fields.keys())
    new_field_names = set(new_fields.keys())
    
    # Check for removed fields
    removed_fields = old_field_names - new_field_names
    for field_name in removed_fields:
        old_field = old_fields[field_name]
        if old_field.get("required", False):
            issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                "Required field removed",
                field_name
            ))
        else:
            issues.append(CompatibilityIssue(
                CompatibilityIssue.WARNING,
                "Optional field removed",
                field_name
            ))
    
    # Check for modified fields
    common_fields = old_field_names & new_field_names
    for field_name in common_fields:
        old_field = old_fields[field_name]
        new_field = new_fields[field_name]
        
        # Check type changes
        old_type = old_field.get("type")
        new_type = new_field.get("type")
        if old_type != new_type:
            issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                f"Type changed from {old_type} to {new_type}",
                field_name
            ))
        
        # Check required flag changes
        old_required = old_field.get("required", False)
        new_required = new_field.get("required", False)
        if not old_required and new_required:
            issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                "Optional field changed to required",
                field_name
            ))
        
        # Check default value changes
        old_default = old_field.get("default")
        new_default = new_field.get("default")
        if old_default != new_default:
            if new_required:
                issues.append(CompatibilityIssue(
                    CompatibilityIssue.BREAKING,
                    f"Default value changed for required field: {old_default} -> {new_default}",
                    field_name
                ))
            else:
                issues.append(CompatibilityIssue(
                    CompatibilityIssue.WARNING,
                    f"Default value changed: {old_default} -> {new_default}",
                    field_name
                ))
        
        # Check for deprecation
        if new_field.get("deprecated", False) and not old_field.get("deprecated", False):
            issues.append(CompatibilityIssue(
                CompatibilityIssue.WARNING,
                "Field marked as deprecated",
                field_name
            ))
    
    # Check for added required fields
    added_fields = new_field_names - old_field_names
    for field_name in added_fields:
        new_field = new_fields[field_name]
        if new_field.get("required", False):
            issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                "New required field added",
                field_name
            ))
    
    return issues


def check_version_bump_adequate(
    old_version: str,
    new_version: str,
    issues: List[CompatibilityIssue]
) -> List[CompatibilityIssue]:
    """Check if version bump is adequate for the changes.
    
    Args:
        old_version: Previous schema version
        new_version: New schema version
        issues: List of compatibility issues
        
    Returns:
        Additional issues if version bump is inadequate
    """
    additional_issues = []
    
    try:
        old_parts = _parse_semver(old_version)
        new_parts = _parse_semver(new_version)
    except ValueError:
        # Invalid version format, skip check
        return additional_issues
    
    has_breaking_changes = any(
        issue.severity == CompatibilityIssue.BREAKING
        for issue in issues
    )
    
    # Check if MAJOR version was bumped for breaking changes
    if has_breaking_changes:
        if new_parts[0] <= old_parts[0]:
            additional_issues.append(CompatibilityIssue(
                CompatibilityIssue.BREAKING,
                f"Breaking changes require MAJOR version bump (current: {old_version} -> {new_version})"
            ))
    
    return additional_issues


def main():
    """CLI entry point for compatibility checker."""
    parser = argparse.ArgumentParser(
        description="Check configuration schema compatibility"
    )
    parser.add_argument(
        "--old",
        required=True,
        help="Path to old schema file"
    )
    parser.add_argument(
        "--new",
        required=True,
        help="Path to new schema file"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error on warnings (not just breaking changes)"
    )
    
    args = parser.parse_args()
    
    # Load schemas
    try:
        with open(args.old, "r") as f:
            old_schema = json.load(f)
        with open(args.new, "r") as f:
            new_schema = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Check compatibility
    issues = check_schema_compatibility(old_schema, new_schema)
    
    # Check version bump adequacy
    old_version = old_schema.get("schema_version")
    new_version = new_schema.get("schema_version")
    
    if old_version and new_version:
        version_issues = check_version_bump_adequate(old_version, new_version, issues)
        issues.extend(version_issues)
    
    # Report issues
    if not issues:
        print("✓ No compatibility issues found")
        sys.exit(0)
    
    breaking_count = sum(1 for i in issues if i.severity == CompatibilityIssue.BREAKING)
    warning_count = sum(1 for i in issues if i.severity == CompatibilityIssue.WARNING)
    
    print(f"Found {len(issues)} compatibility issue(s):")
    print(f"  - {breaking_count} breaking change(s)")
    print(f"  - {warning_count} warning(s)")
    print()
    
    for issue in issues:
        print(f"  {issue}")
    
    # Exit with error if breaking changes found or strict mode with warnings
    if breaking_count > 0:
        sys.exit(1)
    elif args.strict and warning_count > 0:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
