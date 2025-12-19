# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local filesystem secret provider."""

from pathlib import Path
from typing import Optional

from copilot_logging import create_logger

from .provider import SecretProvider
from .exceptions import SecretNotFoundError, SecretProviderError

logger = create_logger(logger_type="stdout", level="INFO", name="copilot_secrets.local")


class LocalFileSecretProvider(SecretProvider):
    """Secret provider that reads secrets from local filesystem.
    
    Secrets are stored as individual files in a base directory. Each file
    contains one secret, with the filename serving as the secret name.
    
    This provider is suitable for:
    - Docker volume-mounted secrets
    - Kubernetes mounted secrets
    - Local development with file-based secrets
    
    Example:
        >>> provider = LocalFileSecretProvider(base_path="/run/secrets")
        >>> jwt_key = provider.get_secret("jwt_private_key")
        >>> # Reads from /run/secrets/jwt_private_key
    
    Attributes:
        base_path: Directory containing secret files
    """
    
    def __init__(self, base_path: str):
        """Initialize the local file secret provider.
        
        Args:
            base_path: Base directory containing secret files
        
        Raises:
            SecretProviderError: If base_path does not exist or is not a directory
        """
        self.base_path = Path(base_path)
        
        if not self.base_path.exists():
            raise SecretProviderError(f"Secret base path does not exist: {base_path}")
        
        if not self.base_path.is_dir():
            raise SecretProviderError(f"Secret base path is not a directory: {base_path}")
        
        logger.info(f"Initialized local secret provider with base path: {base_path}")
    
    def _get_secret_path(self, secret_name: str) -> Path:
        """Get the filesystem path for a secret.
        
        Args:
            secret_name: Name of the secret
        
        Returns:
            Path to the secret file
        
        Raises:
            SecretProviderError: If secret_name contains path traversal attempts
        """
        # Construct potential path and resolve to absolute path
        potential_path = (self.base_path / secret_name).resolve()
        base_resolved = self.base_path.resolve()
        
        # Ensure the resolved path is within the base directory
        try:
            potential_path.relative_to(base_resolved)
        except ValueError as e:
            raise SecretProviderError(
                f"Invalid secret name (path traversal detected): {secret_name}"
            ) from e
        
        return potential_path
    
    def get_secret(self, secret_name: str, version: Optional[str] = None) -> str:
        """Retrieve a secret by name.
        
        Args:
            secret_name: Name of the secret (filename in base_path)
            version: Ignored for local filesystem provider
        
        Returns:
            Secret value as a string (whitespace stripped)
        
        Raises:
            SecretNotFoundError: If the secret file does not exist
            SecretProviderError: If reading the file fails
        """
        secret_path = self._get_secret_path(secret_name)
        
        if not secret_path.exists():
            raise SecretNotFoundError(f"Secret not found: {secret_name}")
        
        if not secret_path.is_file():
            raise SecretProviderError(f"Secret path is not a file: {secret_name}")
        
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            return content
        
        except OSError as e:
            raise SecretProviderError(f"Failed to read secret {secret_name}: {e}") from e
    
    def get_secret_bytes(self, secret_name: str, version: Optional[str] = None) -> bytes:
        """Retrieve a secret as raw bytes.
        
        Args:
            secret_name: Name of the secret (filename in base_path)
            version: Ignored for local filesystem provider
        
        Returns:
            Secret value as bytes
        
        Raises:
            SecretNotFoundError: If the secret file does not exist
            SecretProviderError: If reading the file fails
        """
        secret_path = self._get_secret_path(secret_name)
        
        if not secret_path.exists():
            raise SecretNotFoundError(f"Secret not found: {secret_name}")
        
        if not secret_path.is_file():
            raise SecretProviderError(f"Secret path is not a file: {secret_name}")
        
        try:
            with open(secret_path, "rb") as f:
                content = f.read()
            return content
        
        except OSError as e:
            raise SecretProviderError(f"Failed to read secret {secret_name}: {e}") from e
    
    def secret_exists(self, secret_name: str) -> bool:
        """Check if a secret exists.
        
        Args:
            secret_name: Name of the secret
        
        Returns:
            True if secret file exists and is readable, False otherwise
        """
        try:
            secret_path = self._get_secret_path(secret_name)
            return secret_path.is_file()
        except SecretProviderError:
            return False
