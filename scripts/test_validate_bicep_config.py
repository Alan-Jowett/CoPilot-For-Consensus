# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for scripts/validate_bicep_config.py.

These are intentionally narrow tests covering driver schemas that use:
- root-level discriminant
- oneOf variants selected by the discriminant

This is the pattern used by the Azure Blob archive driver schema.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_validator_module():
    module_path = Path(__file__).resolve().parent / "validate_bicep_config.py"
    spec = importlib.util.spec_from_file_location("validate_bicep_config", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_azureblob_requires_auth_discriminant_env_var():
    v = _load_validator_module()

    # Minimal service schema containing only archive_store.
    service_schema = {
        "adapters": {
            "archive_store": {"$ref": "../adapters/archive_store.json"},
        }
    }

    # Select the azureblob driver, but omit AZUREBLOB_AUTH_TYPE.
    env_vars = {
        "ARCHIVE_STORE_TYPE": "azureblob",
        "AZUREBLOB_ACCOUNT_NAME": "mystorage",
        "AZUREBLOB_CONTAINER_NAME": "archives",
    }

    issues = v.validate_config(env_vars, service_schema, service_name="test")

    assert any("AZUREBLOB_AUTH_TYPE" in issue for issue in issues), issues


def test_archive_azureblob_managed_identity_requires_account_name():
    v = _load_validator_module()

    service_schema = {
        "adapters": {
            "archive_store": {"$ref": "../adapters/archive_store.json"},
        }
    }

    # Now provide AZUREBLOB_AUTH_TYPE so the validator can select the oneOf variant.
    env_vars = {
        "ARCHIVE_STORE_TYPE": "azureblob",
        "AZUREBLOB_AUTH_TYPE": "managed_identity",
        # Missing AZUREBLOB_ACCOUNT_NAME (required for managed_identity variant)
        "AZUREBLOB_CONTAINER_NAME": "archives",
    }

    issues = v.validate_config(env_vars, service_schema, service_name="test")

    assert any("AZUREBLOB_ACCOUNT_NAME" in issue for issue in issues), issues


def test_archive_azureblob_managed_identity_allows_account_name_present():
    v = _load_validator_module()

    service_schema = {
        "adapters": {
            "archive_store": {"$ref": "../adapters/archive_store.json"},
        }
    }

    env_vars = {
        "ARCHIVE_STORE_TYPE": "azureblob",
        "AZUREBLOB_AUTH_TYPE": "managed_identity",
        "AZUREBLOB_ACCOUNT_NAME": "mystorage",
        "AZUREBLOB_CONTAINER_NAME": "archives",
    }

    issues = v.validate_config(env_vars, service_schema, service_name="test")

    assert issues == [], issues


def test_archive_azureblob_invalid_auth_type_is_flagged():
    v = _load_validator_module()

    service_schema = {
        "adapters": {
            "archive_store": {"$ref": "../adapters/archive_store.json"},
        }
    }

    env_vars = {
        "ARCHIVE_STORE_TYPE": "azureblob",
        "AZUREBLOB_AUTH_TYPE": "totally_not_real",
    }

    issues = v.validate_config(env_vars, service_schema, service_name="test")
    assert issues
    assert any("Invalid discriminant value" in issue for issue in issues)


def test_strip_bicep_comments_removes_line_and_block_comments():
    v = _load_validator_module()

    content = """
param x string // line comment
/* block comment */
resource r 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/should-stay'
}
"""
    stripped = v._strip_bicep_comments(content)
    assert "line comment" not in stripped
    assert "block comment" not in stripped
    assert "should-stay" in stripped


def test_strip_bicep_comments_does_not_remove_comment_markers_inside_strings():
    v = _load_validator_module()

    content = r"""
param x string = 'https://example.com/path//not-a-comment'
param y string = "value /* not a comment */ end"
"""
    stripped = v._strip_bicep_comments(content)
    assert "//not-a-comment" in stripped
    assert "/* not a comment */" in stripped


def test_strip_bicep_comments_handles_unterminated_block_comment():
    v = _load_validator_module()

    content = """
param x string = 'ok'
/* starts but never ends
resource r 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/should-not-appear'
}
"""
    stripped = v._strip_bicep_comments(content)
    assert "ok" in stripped
    assert "should-not-appear" not in stripped


def test_strip_bicep_comments_handles_escaped_quotes_with_backslashes():
    v = _load_validator_module()

    # The " inside the string is escaped; the quote after \\ is not escaped.
    content = r"""
param x string = "foo\\\"bar\\\\"  // comment should be removed
param y string = 'still-here'
"""
    stripped = v._strip_bicep_comments(content)
    assert "comment should be removed" not in stripped
    assert "still-here" in stripped
