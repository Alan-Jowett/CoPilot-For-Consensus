# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors
"""Integration tests for Key Vault JWT signing.

These tests are marked as integration and are expected to be skipped unless the
Azure Key Vault SDK dependencies are installed.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.integration]


def test_keyvault_signer_importable():
    """`copilot_jwt_signer` should be importable when installed."""
    pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")
    from copilot_jwt_signer import KeyVaultJWTSigner, create_jwt_signer

    assert KeyVaultJWTSigner is not None
    assert create_jwt_signer is not None


def test_context_manager_support():
    """`KeyVaultJWTSigner` should support the context manager protocol."""
    pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")

    pytest.importorskip("azure.identity", reason="Azure SDK not installed")
    pytest.importorskip("azure.keyvault.keys", reason="Azure Key Vault SDK not installed")
    pytest.importorskip(
        "azure.keyvault.keys.crypto",
        reason="Azure Key Vault cryptography SDK not installed",
    )

    with (
        patch("azure.identity.DefaultAzureCredential"),
        patch("azure.keyvault.keys.KeyClient") as mock_key_client,
        patch("azure.keyvault.keys.crypto.CryptographyClient"),
    ):
        mock_key = Mock()
        mock_key.id = "https://test.vault.azure.net/keys/test-key/version123"
        mock_key_client.return_value.get_key.return_value = mock_key

        from copilot_jwt_signer import KeyVaultJWTSigner

        with patch.object(KeyVaultJWTSigner, "close") as mock_close:
            with KeyVaultJWTSigner(
                algorithm="RS256",
                key_vault_url="https://test.vault.azure.net/",
                key_name="test-key",
            ) as signer:
                assert signer is not None
                assert hasattr(signer, "sign")

            assert mock_close.called
