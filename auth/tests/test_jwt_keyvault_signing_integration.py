# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for JWT signing with Key Vault.

Notes:
- `copilot_jwt_signer` (and the Azure SDK extras it depends on) are optional.
- The auth service configuration schema does not currently expose a `jwt_signer` adapter,
  so these tests focus only on the signer package itself.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

pytestmark = [pytest.mark.integration]


class TestJWTKeyVaultSigningIntegration:
    """Integration tests for Key Vault JWT signer adapter (optional dependency)."""

    def test_keyvault_signer_importable(self):
        """`copilot_jwt_signer` should be importable when installed."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")
        from copilot_jwt_signer import KeyVaultJWTSigner, create_jwt_signer

        assert KeyVaultJWTSigner is not None
        assert create_jwt_signer is not None

    def test_context_manager_support(self):
        """Test that `KeyVaultJWTSigner` supports the context manager protocol."""
        pytest.importorskip("copilot_jwt_signer", reason="copilot_jwt_signer not installed")

        # These are optional extras; skip cleanly if not installed.
        pytest.importorskip("azure.identity", reason="Azure SDK not installed")
        pytest.importorskip("azure.keyvault.keys", reason="Azure Key Vault SDK not installed")
        pytest.importorskip(
            "azure.keyvault.keys.crypto",
            reason="Azure Key Vault cryptography SDK not installed",
        )

        # Mock Azure SDK to avoid actual Key Vault calls.
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
