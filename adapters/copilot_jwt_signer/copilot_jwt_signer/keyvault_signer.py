# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Key Vault JWT signing implementation."""

import base64
import hashlib
import time
from typing import Any

from copilot_logging import create_logger

from .exceptions import CircuitBreakerOpenError, KeyVaultSignerError
from .signer import JWTSigner

logger = create_logger(logger_type="stdout", level="INFO", name="copilot_jwt_signer.keyvault")


class CircuitBreaker:
    """Simple circuit breaker for Key Vault operations.
    
    Prevents cascading failures by opening the circuit after a threshold
    of consecutive failures. The circuit automatically closes after a timeout.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail immediately
    - HALF_OPEN: Testing if service has recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
    ):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening
            timeout_seconds: Time to wait before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout_seconds:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = "HALF_OPEN"
            else:
                remaining_timeout = max(
                    0.0,
                    self.timeout_seconds - (time.time() - self.last_failure_time),
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Will retry after "
                    f"{remaining_timeout:.0f} seconds"
                )
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset failure count and close circuit
            if self.state == "HALF_OPEN":
                logger.info("Circuit breaker transitioning to CLOSED")
            
            self.failure_count = 0
            self.state = "CLOSED"
            return result
            
        except Exception as e:
            # Failure - increment count and potentially open circuit
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker opening after {self.failure_count} failures"
                )
                self.state = "OPEN"
            
            raise


class KeyVaultJWTSigner(JWTSigner):
    """Azure Key Vault JWT signer using cryptographic operations.
    
    This signer uses Azure Key Vault's sign operation to generate JWT
    signatures without ever exposing the private key. It supports:
    - RSA algorithms: RS256, RS384, RS512
    - EC algorithms: ES256, ES384, ES512
    
    Features:
    - Retry logic with exponential backoff for transient failures
    - Circuit breaker to prevent cascading failures
    - Health check with dummy sign operation
    - Public key caching for JWKS generation
    - Context manager support for automatic resource cleanup
    
    Attributes:
        algorithm: JWT signing algorithm
        key_id: Key identifier from Key Vault
        key_vault_url: Key Vault URL
        key_name: Name of the key in Key Vault
        key_version: Optional specific version of the key
        crypto_client: Azure CryptographyClient for sign operations
        key_client: Azure KeyClient for key metadata operations
    
    Example:
        >>> with KeyVaultJWTSigner(...) as signer:
        ...     signature = signer.sign(message)
        # Resources automatically released
    """
    
    # Algorithm mapping to Key Vault SignatureAlgorithm
    _ALGORITHM_MAP = {
        "RS256": "RS256",
        "RS384": "RS384",
        "RS512": "RS512",
        "ES256": "ES256",
        "ES384": "ES384",
        "ES512": "ES512",
    }
    
    def __init__(
        self,
        algorithm: str,
        key_vault_url: str,
        key_name: str,
        key_version: str | None = None,
        key_id: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
    ):
        """Initialize Key Vault JWT signer.
        
        Args:
            algorithm: Signing algorithm (RS256, RS384, RS512, ES256, ES384, ES512)
            key_vault_url: Azure Key Vault URL (e.g., "https://my-vault.vault.azure.net/")
            key_name: Name of the key in Key Vault
            key_version: Optional specific version of the key (uses latest if not specified)
            key_id: Key identifier for JWT header (defaults to key_name)
            max_retries: Maximum number of retry attempts for transient failures
            retry_delay: Initial delay between retries (exponential backoff)
            circuit_breaker_threshold: Number of failures before opening circuit
            circuit_breaker_timeout: Seconds to wait before retrying after circuit opens
            
        Raises:
            KeyVaultSignerError: If algorithm is unsupported or Key Vault client initialization fails
            
        Note:
            Public keys are cached indefinitely. When using key_version=None (latest),
            the service must be restarted after key rotation to pick up the new key version.
            For zero-downtime key rotation, specify an explicit key_version.
        """
        # Validate algorithm
        if algorithm not in self._ALGORITHM_MAP:
            raise KeyVaultSignerError(
                f"Unsupported algorithm: {algorithm}. "
                f"Supported: {', '.join(self._ALGORITHM_MAP.keys())}"
            )
        
        super().__init__(algorithm, key_id or key_name)
        
        self.key_vault_url = key_vault_url
        self.key_name = key_name
        self.key_version = key_version
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout_seconds=circuit_breaker_timeout,
        )
        
        # Cache for public key
        self._public_key_cache = None
        
        # Initialize Azure clients
        self._initialize_clients()
    
    def _initialize_clients(self) -> None:
        """Initialize Azure Key Vault clients.
        
        Raises:
            KeyVaultSignerError: If Azure SDK dependencies are not installed
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys import KeyClient
            from azure.keyvault.keys.crypto import CryptographyClient
        except ImportError as e:
            raise KeyVaultSignerError(
                "Azure SDK dependencies for Key Vault are not installed. "
                "Install with: pip install copilot-jwt-signer[azure]"
            ) from e
        
        try:
            # Initialize credential
            self._credential = DefaultAzureCredential()
            
            # Initialize key client for metadata operations
            self.key_client = KeyClient(
                vault_url=self.key_vault_url,
                credential=self._credential
            )
            
            # Get full key identifier
            # When key_version is None, use versionless key identifier
            # CryptographyClient will lazily resolve the latest version on first use
            # This avoids blocking on a Key Vault network call during initialization
            if self.key_version:
                key_id = f"{self.key_vault_url}/keys/{self.key_name}/{self.key_version}"
            else:
                key_id = f"{self.key_vault_url}/keys/{self.key_name}"
            
            # Initialize cryptography client for sign operations
            self.crypto_client = CryptographyClient(
                key=key_id,
                credential=self._credential
            )
            
            logger.info(
                f"Initialized Key Vault JWT signer for {self.algorithm} "
                f"with key {self.key_name} in {self.key_vault_url}"
            )
            
        except Exception as e:
            raise KeyVaultSignerError(
                f"Failed to initialize Key Vault clients: {e}"
            ) from e
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message using Key Vault cryptographic operation.
        
        Args:
            message: Raw message bytes to sign
            
        Returns:
            Signature bytes
            
        Raises:
            KeyVaultSignerError: If signing fails
            SigningTimeoutError: If signing times out
            CircuitBreakerOpenError: If circuit breaker is open
        """
        from azure.keyvault.keys.crypto import SignatureAlgorithm
        
        # Map algorithm to Key Vault SignatureAlgorithm
        kv_algorithm = getattr(SignatureAlgorithm, self._ALGORITHM_MAP[self.algorithm])
        
        # Hash the message locally (Key Vault expects pre-hashed input for some algorithms)
        digest = self._hash_message(message)
        
        # Perform sign operation with circuit breaker protection
        def _sign_with_retry():
            last_error = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    # Call Key Vault sign operation
                    result = self.crypto_client.sign(kv_algorithm, digest)
                    return result.signature
                    
                except Exception as e:
                    last_error = e
                    
                    # Check if this is a transient error worth retrying
                    if attempt < self.max_retries and self._is_transient_error(e):
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Key Vault sign operation failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                            f"retrying in {delay:.1f}s: {e}"
                        )
                        time.sleep(delay)
                        continue
                    
                    # Non-transient error or max retries exceeded
                    raise KeyVaultSignerError(
                        f"Key Vault sign operation failed after {attempt + 1} attempts: {e}"
                    ) from e
            
            # Should not reach here, but just in case
            raise KeyVaultSignerError(
                f"Key Vault sign operation failed: {last_error}"
            ) from last_error
        
        try:
            return self.circuit_breaker.call(_sign_with_retry)
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            raise KeyVaultSignerError(f"Signing failed: {e}") from e
    
    def _hash_message(self, message: bytes) -> bytes:
        """Hash message according to algorithm.
        
        Args:
            message: Message bytes to hash
            
        Returns:
            Hashed message bytes
        """
        if self.algorithm in ("RS256", "ES256"):
            return hashlib.sha256(message).digest()
        elif self.algorithm in ("RS384", "ES384"):
            return hashlib.sha384(message).digest()
        elif self.algorithm in ("RS512", "ES512"):
            return hashlib.sha512(message).digest()
        else:
            raise KeyVaultSignerError(f"Unsupported algorithm for hashing: {self.algorithm}")
    
    @staticmethod
    def _is_transient_error(error: Exception) -> bool:
        """Check if error is transient and worth retrying.
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is transient
        """
        # Import Azure exceptions for error checking
        try:
            from azure.core.exceptions import (
                ClientAuthenticationError,
                HttpResponseError,
                ServiceRequestError,
            )
        except ImportError:
            return False
        
        # Network errors and service unavailable are transient
        if isinstance(error, (ServiceRequestError, ConnectionError, TimeoutError)):
            return True
        
        # HTTP 5xx errors are typically transient
        if isinstance(error, HttpResponseError):
            if error.status_code and 500 <= error.status_code < 600:
                return True
        
        # Don't retry authentication errors
        if isinstance(error, ClientAuthenticationError):
            return False
        
        return False
    
    def get_public_key_jwk(self) -> dict[str, Any]:
        """Get public key in JWK format from Key Vault.
        
        Returns:
            JWK dictionary with public key parameters
            
        Raises:
            KeyVaultSignerError: If public key retrieval fails
        """
        try:
            # Use cached public key if available
            if self._public_key_cache:
                return self._public_key_cache
            
            # Fetch key from Key Vault
            key = self.key_client.get_key(self.key_name, version=self.key_version)
            
            # Convert to JWK format
            jwk = {
                "kty": key.key_type.value if hasattr(key.key_type, 'value') else str(key.key_type),
                "use": "sig",
                "kid": self.key_id,
                "alg": self.algorithm,
            }
            
            # Add key-specific parameters
            if key.key_type.value == "RSA":
                jwk["n"] = self._bytes_to_base64url(key.key.n)
                jwk["e"] = self._bytes_to_base64url(key.key.e)
            elif key.key_type.value == "EC":
                jwk["crv"] = key.key.crv.value if hasattr(key.key.crv, 'value') else str(key.key.crv)
                jwk["x"] = self._bytes_to_base64url(key.key.x)
                jwk["y"] = self._bytes_to_base64url(key.key.y)
            
            # Cache the result
            self._public_key_cache = jwk
            
            return jwk
            
        except Exception as e:
            raise KeyVaultSignerError(f"Failed to get public key JWK: {e}") from e
    
    @staticmethod
    def _bytes_to_base64url(value: bytes) -> str:
        """Convert bytes to base64url-encoded string."""
        return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')
    
    def get_public_key_pem(self) -> str | None:
        """Get public key in PEM format from Key Vault.
        
        Returns:
            Public key in PEM format
            
        Raises:
            KeyVaultSignerError: If public key retrieval fails
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
        
        try:
            # Fetch key from Key Vault
            key = self.key_client.get_key(self.key_name, version=self.key_version)
            
            # Convert to PEM format using cryptography library
            if key.key_type.value == "RSA":
                # Reconstruct RSA public key
                public_key = rsa.RSAPublicNumbers(
                    e=int.from_bytes(key.key.e, byteorder='big'),
                    n=int.from_bytes(key.key.n, byteorder='big')
                ).public_key()
            elif key.key_type.value == "EC":
                # Reconstruct EC public key
                # Map curve name
                curve_name = key.key.crv.value if hasattr(key.key.crv, 'value') else str(key.key.crv)
                if curve_name == "P-256":
                    curve = ec.SECP256R1()
                elif curve_name == "P-384":
                    curve = ec.SECP384R1()
                elif curve_name == "P-521":
                    curve = ec.SECP521R1()
                else:
                    raise KeyVaultSignerError(f"Unsupported EC curve: {curve_name}")
                
                public_key = ec.EllipticCurvePublicNumbers(
                    x=int.from_bytes(key.key.x, byteorder='big'),
                    y=int.from_bytes(key.key.y, byteorder='big'),
                    curve=curve
                ).public_key()
            else:
                raise KeyVaultSignerError(f"Unsupported key type: {key.key_type}")
            
            # Export to PEM format
            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return pem.decode('utf-8')
            
        except Exception as e:
            raise KeyVaultSignerError(f"Failed to get public key PEM: {e}") from e
    
    def close(self) -> None:
        """Release resources held by this signer."""
        # Close the crypto client
        crypto_client = getattr(self, "crypto_client", None)
        if crypto_client is not None:
            close_method = getattr(crypto_client, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except TypeError as e:
                    # Unexpected - typically indicates a bug in the code
                    logger.warning(f"Unexpected TypeError closing crypto client: {e}")
                except Exception as e:
                    # Other unexpected errors - log but don't raise
                    logger.warning(f"Unexpected error closing crypto client: {e}")
        
        # Close the key client
        key_client = getattr(self, "key_client", None)
        if key_client is not None:
            close_method = getattr(key_client, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except TypeError as e:
                    # Unexpected - typically indicates a bug in the code
                    logger.warning(f"Unexpected TypeError closing key client: {e}")
                except Exception as e:
                    # Other unexpected errors - log but don't raise
                    logger.warning(f"Unexpected error closing key client: {e}")
        
        # Close the credential
        credential = getattr(self, "_credential", None)
        if credential is not None:
            close_method = getattr(credential, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except TypeError as e:
                    # Unexpected - typically indicates a bug in the code
                    logger.warning(f"Unexpected TypeError closing credential: {e}")
                except Exception as e:
                    # Other unexpected errors - log but don't raise
                    logger.warning(f"Unexpected error closing credential: {e}")
    
    def __enter__(self):
        """Enter context manager - returns self for use in with statement."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - automatically releases resources.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
            
        Returns:
            False to propagate any exception that occurred
        """
        self.close()
        return False
