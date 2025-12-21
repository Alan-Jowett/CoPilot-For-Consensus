# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema compatibility checker."""

import json
import pytest

from copilot_config.check_compat import (
    CompatibilityIssue,
    check_schema_compatibility,
    check_version_bump_adequate,
)


class TestCompatibilityChecker:
    """Tests for schema compatibility checking."""

    def test_no_changes_no_issues(self):
        """Test that identical schemas have no issues."""
        schema = {
            "service_name": "test",
            "schema_version": "1.0.0",
            "fields": {
                "field1": {"type": "string", "default": "test"},
            },
        }
        
        issues = check_schema_compatibility(schema, schema)
        
        assert len(issues) == 0

    def test_field_removal_breaking(self):
        """Test that removing a required field is breaking."""
        old_schema = {
            "fields": {
                "field1": {"type": "string", "required": True},
            },
        }
        new_schema = {
            "fields": {},
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "field1" in breaking[0].field

    def test_optional_field_removal_warning(self):
        """Test that removing an optional field is a warning."""
        old_schema = {
            "fields": {
                "field1": {"type": "string", "required": False},
            },
        }
        new_schema = {
            "fields": {},
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        warnings = [i for i in issues if i.severity == CompatibilityIssue.WARNING]
        assert len(warnings) == 1
        assert "field1" in warnings[0].field

    def test_type_change_breaking(self):
        """Test that changing field type is breaking."""
        old_schema = {
            "fields": {
                "field1": {"type": "string"},
            },
        }
        new_schema = {
            "fields": {
                "field1": {"type": "int"},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "Type changed" in breaking[0].message

    def test_making_field_required_breaking(self):
        """Test that making optional field required is breaking."""
        old_schema = {
            "fields": {
                "field1": {"type": "string", "required": False},
            },
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "required": True},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "required" in breaking[0].message.lower()

    def test_adding_required_field_breaking(self):
        """Test that adding a required field is breaking."""
        old_schema = {
            "fields": {},
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "required": True},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "required" in breaking[0].message.lower()

    def test_adding_optional_field_ok(self):
        """Test that adding an optional field is OK."""
        old_schema = {
            "fields": {},
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "required": False},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        # Should have no breaking changes
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 0

    def test_default_value_change_required_breaking(self):
        """Test that changing default for required field is breaking."""
        old_schema = {
            "fields": {
                "field1": {"type": "string", "required": True, "default": "old"},
            },
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "required": True, "default": "new"},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "Default value changed" in breaking[0].message

    def test_default_value_change_optional_warning(self):
        """Test that changing default for optional field is a warning."""
        old_schema = {
            "fields": {
                "field1": {"type": "string", "required": False, "default": "old"},
            },
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "required": False, "default": "new"},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        warnings = [i for i in issues if i.severity == CompatibilityIssue.WARNING]
        assert len(warnings) == 1
        assert "Default value changed" in warnings[0].message

    def test_field_deprecation_warning(self):
        """Test that deprecating a field is a warning."""
        old_schema = {
            "fields": {
                "field1": {"type": "string"},
            },
        }
        new_schema = {
            "fields": {
                "field1": {"type": "string", "deprecated": True},
            },
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        warnings = [i for i in issues if i.severity == CompatibilityIssue.WARNING]
        assert len(warnings) == 1
        assert "deprecated" in warnings[0].message.lower()

    def test_version_downgrade_breaking(self):
        """Test that version downgrade is breaking."""
        old_schema = {
            "schema_version": "2.0.0",
            "fields": {},
        }
        new_schema = {
            "schema_version": "1.0.0",
            "fields": {},
        }
        
        issues = check_schema_compatibility(old_schema, new_schema)
        
        breaking = [i for i in issues if i.severity == CompatibilityIssue.BREAKING]
        assert len(breaking) == 1
        assert "downgrade" in breaking[0].message.lower()


class TestVersionBumpAdequacy:
    """Tests for version bump adequacy checking."""

    def test_breaking_change_requires_major_bump(self):
        """Test that breaking changes require MAJOR version bump."""
        issues = [
            CompatibilityIssue(CompatibilityIssue.BREAKING, "Breaking change"),
        ]
        
        # Minor bump is not adequate
        version_issues = check_version_bump_adequate("1.0.0", "1.1.0", issues)
        assert len(version_issues) > 0
        assert "MAJOR" in version_issues[0].message
        
        # Major bump is adequate
        version_issues = check_version_bump_adequate("1.0.0", "2.0.0", issues)
        assert len(version_issues) == 0

    def test_no_breaking_changes_no_major_required(self):
        """Test that non-breaking changes don't require MAJOR bump."""
        issues = [
            CompatibilityIssue(CompatibilityIssue.WARNING, "Warning"),
        ]
        
        # Minor bump is fine for warnings
        version_issues = check_version_bump_adequate("1.0.0", "1.1.0", issues)
        assert len(version_issues) == 0
