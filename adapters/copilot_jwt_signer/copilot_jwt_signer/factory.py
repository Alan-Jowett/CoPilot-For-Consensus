# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating JWT signer instances."""

from pathlib import Path

from copilot_logging import create_logger

from .exceptions import JWTSignerError
from .local_signer import LocalJWTSigner
from .signer import JWTSigner

logger = create_logger(logger_type="stdout", level="INFO", name="copilot_jwt_signer.factory")


def create_jwt_signer(
    signer_type: str,
    algorithm: str,
    key_id: str = "default",
    **kwargs
) -> JWTSigner:
    """Create a JWT signer instance based on configuration.
    
    Args:
        signer_type: Type of signer to create ("local" or "keyvault")
        algorithm: JWT signing algorithm (e.g., "RS256", "ES256", "HS256")
        key_id: Key identifier for rotation support
        **kwargs: Additional signer-specific parameters
        
    Returns:
        JWTSigner instance
        
    Raises:
        JWTSignerError: If signer type is unknown or configuration is invalid
        
    Examples:
        >>> # Create local RSA signer
        >>> signer = create_jwt_signer(
        ...     signer_type="local",
        ...     algorithm="RS256",
        ...     private_key_path="/path/to/private.pem",
        ...     public_key_path="/path/to/public.pem"
        ... )
        
        >>> # Create Key Vault signer
        >>> signer = create_jwt_signer(
        ...     signer_type="keyvault",
        ...     algorithm="RS256",
        ...     key_vault_url="https://my-vault.vault.azure.net/",
        ...     key_name="jwt-signing-key"
        ... )
        
        >>> # Create local HMAC signer
        >>> signer = create_jwt_signer(
        ...     signer_type="local",
        ...     algorithm="HS256",
        ...     secret_key="my-secret-key"
        ... )
    """
    signer_type = signer_type.lower()
    
    logger.info(f"Creating JWT signer: type={signer_type}, algorithm={algorithm}, key_id={key_id}")
    
    if signer_type == "local":
        return _create_local_signer(algorithm, key_id, **kwargs)
    elif signer_type == "keyvault":
        return _create_keyvault_signer(algorithm, key_id, **kwargs)
    else:
        raise JWTSignerError(
            f"Unknown signer type: {signer_type}. "
            f"Supported types: local, keyvault"
        )


def _create_local_signer(algorithm: str, key_id: str, **kwargs) -> LocalJWTSigner:
    """Create a local file-based JWT signer.
    
    Args:
        algorithm: JWT signing algorithm
        key_id: Key identifier
        **kwargs: Additional parameters
            - private_key_path: Path to private key (for RSA/EC)
            - public_key_path: Path to public key (for RSA/EC)
            - secret_key: HMAC secret (for HS256/HS384/HS512)
            
    Returns:
        LocalJWTSigner instance
        
    Raises:
        JWTSignerError: If required parameters are missing
    """
    if algorithm.startswith("RS") or algorithm.startswith("ES"):
        # Asymmetric algorithms require key files
        private_key_path = kwargs.get("private_key_path")
        public_key_path = kwargs.get("public_key_path")
        
        if not private_key_path:
            raise JWTSignerError(
                f"{algorithm} requires private_key_path parameter"
            )
        if not public_key_path:
            raise JWTSignerError(
                f"{algorithm} requires public_key_path parameter"
            )
        
        return LocalJWTSigner(
            algorithm=algorithm,
            private_key_path=Path(private_key_path),
            public_key_path=Path(public_key_path),
            key_id=key_id,
        )
        
    elif algorithm.startswith("HS"):
        # Symmetric algorithms use HMAC secret
        secret_key = kwargs.get("secret_key")
        
        if not secret_key:
            raise JWTSignerError(
                f"{algorithm} requires secret_key parameter"
            )
        
        return LocalJWTSigner(
            algorithm=algorithm,
            secret_key=secret_key,
            key_id=key_id,
        )
        
    else:
        raise JWTSignerError(
            f"Unsupported algorithm for local signer: {algorithm}"
        )


def _create_keyvault_signer(algorithm: str, key_id: str, **kwargs) -> JWTSigner:
    """Create a Key Vault JWT signer.
    
    Args:
        algorithm: JWT signing algorithm
        key_id: Key identifier
        **kwargs: Additional parameters
            - key_vault_url: Azure Key Vault URL (required)
            - key_name: Name of the key in Key Vault (required)
            - key_version: Optional specific version of the key
            - max_retries: Maximum retry attempts (default: 3)
            - retry_delay: Initial retry delay in seconds (default: 1.0)
            - timeout_seconds: Timeout for operations (default: 10.0)
            - circuit_breaker_threshold: Failures before opening circuit (default: 5)
            - circuit_breaker_timeout: Seconds to wait before retry (default: 60)
            
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
    key_vault_url = kwargs.get("key_vault_url")
    if not key_vault_url:
        raise JWTSignerError(
            "Key Vault signer requires key_vault_url parameter. "
            "Provide the Azure Key Vault URL (e.g., 'https://my-vault.vault.azure.net/')"
        )
    
    key_name = kwargs.get("key_name")
    if not key_name:
        raise JWTSignerError(
            "Key Vault signer requires key_name parameter. "
            "Provide the name of the key in Key Vault"
        )
    
    # Create signer with optional parameters
    return KeyVaultJWTSigner(
        algorithm=algorithm,
        key_vault_url=key_vault_url,
        key_name=key_name,
        key_version=kwargs.get("key_version"),
        key_id=key_id,
        max_retries=kwargs.get("max_retries", 3),
        retry_delay=kwargs.get("retry_delay", 1.0),
        timeout_seconds=kwargs.get("timeout_seconds", 10.0),
        circuit_breaker_threshold=kwargs.get("circuit_breaker_threshold", 5),
        circuit_breaker_timeout=kwargs.get("circuit_breaker_timeout", 60),
    )
