# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test fixtures for the copilot_secrets adapter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


@dataclass(frozen=True)
class AzureSdkMocks:
    """Per-test Azure SDK mocks.

    We patch `sys.modules` so `AzureKeyVaultProvider` can import Azure SDK symbols
    without requiring Azure dependencies to be installed.

    The mocks are created per-test to avoid cross-test interference.
    """

    secret_client_cls: MagicMock
    default_credential_cls: MagicMock
    ResourceNotFoundError: type[Exception]
    ClientAuthenticationError: type[Exception]
    AzureError: type[Exception]


@pytest.fixture
def azure_sdk_mocks(monkeypatch: pytest.MonkeyPatch) -> AzureSdkMocks:
    """Provide per-test Azure SDK module mocks via `sys.modules`."""

    secret_client_cls = MagicMock(name="SecretClient")
    default_credential_cls = MagicMock(name="DefaultAzureCredential")

    resource_not_found_error = type("ResourceNotFoundError", (Exception,), {})
    client_auth_error = type("ClientAuthenticationError", (Exception,), {})
    azure_error = type("AzureError", (Exception,), {})

    # Parent/namespace modules
    monkeypatch.setitem(sys.modules, "azure", MagicMock())
    monkeypatch.setitem(sys.modules, "azure.keyvault", MagicMock())
    monkeypatch.setitem(sys.modules, "azure.core", MagicMock())

    # Leaf modules used by the provider.
    monkeypatch.setitem(
        sys.modules,
        "azure.keyvault.secrets",
        MagicMock(SecretClient=secret_client_cls),
    )
    monkeypatch.setitem(
        sys.modules,
        "azure.identity",
        MagicMock(DefaultAzureCredential=default_credential_cls),
    )
    monkeypatch.setitem(
        sys.modules,
        "azure.core.exceptions",
        MagicMock(
            ResourceNotFoundError=resource_not_found_error,
            ClientAuthenticationError=client_auth_error,
            AzureError=azure_error,
        ),
    )

    return AzureSdkMocks(
        secret_client_cls=secret_client_cls,
        default_credential_cls=default_credential_cls,
        ResourceNotFoundError=resource_not_found_error,
        ClientAuthenticationError=client_auth_error,
        AzureError=azure_error,
    )
