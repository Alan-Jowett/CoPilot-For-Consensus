# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating JWT signer instances."""

import logging
from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.jwt_signer import (
    AdapterConfig_JwtSigner,
    DriverConfig_JwtSigner_Keyvault,
    DriverConfig_JwtSigner_Local,
)

from .exceptions import JWTSignerError
from .local_signer import LocalJWTSigner
from .signer import JWTSigner

logger = logging.getLogger("copilot_jwt_signer.factory")


_DriverConfig: TypeAlias = DriverConfig_JwtSigner_Local | DriverConfig_JwtSigner_Keyvault


def _build_local(driver_config: DriverConfig_JwtSigner_Local) -> JWTSigner:
    algorithm = driver_config.algorithm
    key_id = driver_config.key_id

    if algorithm.startswith("RS") or algorithm.startswith("ES"):
        if not driver_config.private_key:
            raise JWTSignerError(f"{algorithm} requires private_key")
        if not driver_config.public_key:
            raise JWTSignerError(f"{algorithm} requires public_key")

        return LocalJWTSigner(
            algorithm=algorithm,
            private_key=driver_config.private_key,
            public_key=driver_config.public_key,
            key_id=key_id,
        )

    if algorithm.startswith("HS"):
        if not driver_config.secret_key:
            raise JWTSignerError(f"{algorithm} requires secret_key")

        return LocalJWTSigner(
            algorithm=algorithm,
            secret_key=driver_config.secret_key,
            key_id=key_id,
        )

    raise JWTSignerError(f"Unsupported algorithm for local signer: {algorithm}")


def _build_keyvault(driver_config: DriverConfig_JwtSigner_Keyvault) -> JWTSigner:
    # Import KeyVaultJWTSigner here to avoid import errors if Azure SDK not installed.
    try:
        from .keyvault_signer import KeyVaultJWTSigner
    except ImportError as exc:
        raise JWTSignerError(
            "Key Vault signer requires Azure SDK dependencies. "
            "Install with: pip install copilot-jwt-signer[azure]"
        ) from exc

    return KeyVaultJWTSigner(
        algorithm=driver_config.algorithm,
        key_vault_url=driver_config.key_vault_url,
        key_name=driver_config.key_name,
        key_version=driver_config.key_version,
        key_id=driver_config.key_id,
        max_retries=driver_config.max_retries,
        retry_delay=driver_config.retry_delay,
        circuit_breaker_threshold=driver_config.circuit_breaker_threshold,
        circuit_breaker_timeout=int(driver_config.circuit_breaker_timeout),
    )


def _build_local_from_union(driver_config: _DriverConfig) -> JWTSigner:
    if not isinstance(driver_config, DriverConfig_JwtSigner_Local):
        raise TypeError("driver config must be DriverConfig_JwtSigner_Local")
    return _build_local(driver_config)


def _build_keyvault_from_union(driver_config: _DriverConfig) -> JWTSigner:
    if not isinstance(driver_config, DriverConfig_JwtSigner_Keyvault):
        raise TypeError("driver config must be DriverConfig_JwtSigner_Keyvault")
    return _build_keyvault(driver_config)


def create_jwt_signer(config: AdapterConfig_JwtSigner) -> JWTSigner:
    """Create a JWT signer instance from typed configuration.

    Args:
        config: Typed adapter configuration for jwt_signer.

    Returns:
        JWTSigner instance.

    Raises:
        ValueError: If config is missing, driver type is unknown, or driver config fails schema validation.
        TypeError: If driver config type does not match the selected driver.
        JWTSignerError: If the driver cannot be created (e.g., missing optional dependencies).

    Examples:
        >>> from copilot_config.generated.adapters.jwt_signer import (
        ...     AdapterConfig_JwtSigner, DriverConfig_JwtSigner_Local
        ... )
        >>> signer = create_jwt_signer(
        ...     AdapterConfig_JwtSigner(
        ...         signer_type="local",
        ...         driver=DriverConfig_JwtSigner_Local(
        ...             algorithm="HS256",
        ...             key_id="default",
        ...             secret_key="super-secret",
        ...         ),
        ...     )
        ... )
    """
    return create_adapter(
        config,
        adapter_name="jwt_signer",
        get_driver_type=lambda c: c.signer_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "local": _build_local_from_union,
            "keyvault": _build_keyvault_from_union,
        },
    )
