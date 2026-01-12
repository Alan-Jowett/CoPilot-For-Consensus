# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating JWT signer instances."""

import logging
from pathlib import Path

from copilot_config import DriverConfig

from .exceptions import JWTSignerError
from .local_signer import LocalJWTSigner
from .signer import JWTSigner

logger = logging.getLogger("copilot_jwt_signer.factory")


def create_jwt_signer(
    driver_name: str,
    driver_config: DriverConfig,
) -> JWTSigner:
    """Create a JWT signer instance based on configuration.

    Args:
        driver_name: Type of signer to create ("local" or "keyvault")
        driver_config: DriverConfig instance with driver configuration

    Returns:
        JWTSigner instance

    Raises:
        JWTSignerError: If driver_name is unknown or configuration is invalid
        ValueError: If required configuration parameters are missing

    Examples:
        >>> from copilot_config import DriverConfig
        >>> # Create local RSA signer
        >>> config = DriverConfig(
        ...     algorithm="RS256",
        ...     key_id="default",
        ...     private_key_path="/path/to/private.pem",
        ...     public_key_path="/path/to/public.pem"
        ... )
        >>> signer = create_jwt_signer("local", config)

        >>> # Create Key Vault signer
        >>> config = DriverConfig(
        ...     algorithm="RS256",
        ...     key_id="default",
        ...     key_vault_url="https://my-vault.vault.azure.net/",
        ...     key_name="jwt-signing-key"
        ... )
        >>> signer = create_jwt_signer("keyvault", config)
    """
    driver_name_lower = driver_name.lower()

    algorithm = getattr(driver_config, "algorithm", "RS256")
    key_id = getattr(driver_config, "key_id", "default")

    logger.info("Creating JWT signer: type=%s, algorithm=%s, key_id=%s", 
                driver_name_lower, algorithm, key_id)

    if driver_name_lower == "local":
        return _create_local_signer(algorithm, key_id, driver_config)
    if driver_name_lower == "keyvault":
        return _create_keyvault_signer(algorithm, key_id, driver_config)

    raise JWTSignerError(
        f"Unknown driver_name: {driver_name}. "
        f"Supported: 'local', 'keyvault'"
    )


def _create_local_signer(
    algorithm: str, 
    key_id: str, 
    driver_config: DriverConfig
) -> LocalJWTSigner:
    """Create a local file-based JWT signer.

    Args:
        algorithm: JWT signing algorithm
        key_id: Key identifier
        driver_config: DriverConfig instance with driver-specific settings

    Returns:
        LocalJWTSigner instance

    Raises:
        JWTSignerError: If required parameters are missing
    """
    if algorithm.startswith("RS") or algorithm.startswith("ES"):
        # Asymmetric algorithms require key files
        private_key_path = getattr(driver_config, "private_key_path", None)
        public_key_path = getattr(driver_config, "public_key_path", None)

        if not private_key_path:
            raise JWTSignerError(
                f"{algorithm} requires private_key_path in driver_config"
            )
        if not public_key_path:
            raise JWTSignerError(
                f"{algorithm} requires public_key_path in driver_config"
            )

        return LocalJWTSigner(
            algorithm=algorithm,
            private_key_path=Path(private_key_path),
            public_key_path=Path(public_key_path),
            key_id=key_id,
        )

    if algorithm.startswith("HS"):
        # Symmetric algorithms use HMAC secret
        secret_key = getattr(driver_config, "secret_key", None)

        if not secret_key:
            raise JWTSignerError(
                f"{algorithm} requires secret_key in driver_config"
            )

        return LocalJWTSigner(
            algorithm=algorithm,
            secret_key=secret_key,
            key_id=key_id,
        )

    raise JWTSignerError(
        f"Unsupported algorithm for local signer: {algorithm}"
    )


def _create_keyvault_signer(
    algorithm: str, 
    key_id: str, 
    driver_config: DriverConfig
) -> JWTSigner:
    """Create a Key Vault JWT signer.

    Args:
        algorithm: JWT signing algorithm
        key_id: Key identifier
        driver_config: DriverConfig instance with Key Vault settings

    Returns:
        KeyVaultJWTSigner instance

    Raises:
        JWTSignerError: If required parameters are missing or Azure SDK not available
    """
    # Import KeyVaultJWTSigner here to avoid import errors if Azure SDK not installed
    try:
        from .keyvault_signer import KeyVaultJWTSigner
    except ImportError as e:
        raise JWTSignerError(
            "Key Vault signer requires Azure SDK dependencies. "
            "Install with: pip install copilot-jwt-signer[azure]"
        ) from e

    # Validate required parameters
    key_vault_url = getattr(driver_config, "key_vault_url", None)
    if not key_vault_url:
        raise JWTSignerError(
            "Key Vault signer requires key_vault_url in driver_config. "
            "Provide the Azure Key Vault URL (e.g., 'https://my-vault.vault.azure.net/')"
        )

    key_name = getattr(driver_config, "key_name", None)
    if not key_name:
        raise JWTSignerError(
            "Key Vault signer requires key_name in driver_config. "
            "Provide the name of the key in Key Vault"
        )

    # Create signer with optional parameters
    return KeyVaultJWTSigner(
        algorithm=algorithm,
        key_vault_url=key_vault_url,
        key_name=key_name,
        key_version=getattr(driver_config, "key_version", None),
        key_id=key_id,
        max_retries=getattr(driver_config, "max_retries", 3),
        retry_delay=getattr(driver_config, "retry_delay", 0.5),
        circuit_breaker_threshold=getattr(driver_config, "circuit_breaker_threshold", 5),
        circuit_breaker_timeout=getattr(driver_config, "circuit_breaker_timeout", 60.0),
    )
