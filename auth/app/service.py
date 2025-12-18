# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service implementation."""

import secrets
from typing import Any, Dict, Optional

from copilot_auth import (
    create_identity_provider,
    IdentityProvider,
    JWTManager,
    OIDCProvider,
    AuthenticationError,
    ProviderError,
)
from copilot_logging import create_logger

from .config import AuthConfig

logger = create_logger(logger_type="stdout", level="INFO", name="auth.service")


class AuthService:
    """Authentication service for OIDC login and JWT minting.
    
    Coordinates multiple OIDC providers and issues local JWTs.
    
    Attributes:
        config: Auth service configuration
        providers: Dictionary of OIDC providers by name
        jwt_manager: JWT token manager
        stats: Service statistics
    """
    
    def __init__(self, config: AuthConfig):
        """Initialize the auth service.
        
        Args:
            config: Auth service configuration
        """
        self.config = config
        self.providers: Dict[str, IdentityProvider] = {}
        self.jwt_manager: Optional[JWTManager] = None
        
        # Statistics
        self.stats = {
            "logins_total": 0,
            "tokens_minted": 0,
            "tokens_validated": 0,
            "validation_failures": 0,
        }
        
        # Session storage (for MVP, in-memory; production should use Redis)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        # Initialize providers and JWT manager
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize OIDC providers and JWT manager."""
        logger.info("Initializing Auth Service...")
        
        # Initialize JWT manager
        self.jwt_manager = JWTManager(
            issuer=self.config.issuer,
            algorithm=self.config.jwt.algorithm,
            private_key_path=self.config.jwt.private_key_path,
            public_key_path=self.config.jwt.public_key_path,
            secret_key=self.config.jwt.secret_key,
            key_id=self.config.jwt.key_id,
            default_expiry=self.config.jwt.default_expiry,
        )
        
        # Initialize OIDC providers
        for provider_name, provider_config in self.config.oidc_providers.items():
            try:
                provider = create_identity_provider(
                    provider_type=provider_config.provider_type,
                    **provider_config.dict()
                )
                
                # Perform OIDC discovery for OIDC providers
                if isinstance(provider, OIDCProvider):
                    provider.discover()
                
                self.providers[provider_name] = provider
                logger.info(f"Initialized provider: {provider_name}")
            
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_name}: {e}")
        
        logger.info(f"Auth Service initialized with {len(self.providers)} providers")
    
    def is_ready(self) -> bool:
        """Check if service is ready to handle requests."""
        return self.jwt_manager is not None and len(self.providers) > 0
    
    def initiate_login(
        self,
        provider: str,
        audience: str,
        prompt: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Initiate OIDC login flow.
        
        Args:
            provider: Provider identifier
            audience: Target audience for JWT
            prompt: Optional OAuth prompt parameter
        
        Returns:
            Tuple of (authorization_url, state, nonce)
        
        Raises:
            ValueError: If provider is unknown
        """
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        provider_instance = self.providers[provider]
        
        if not isinstance(provider_instance, OIDCProvider):
            raise ValueError(f"Provider {provider} does not support OIDC login flow")
        
        # Generate state and nonce
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        
        # Get authorization URL
        authorization_url, state, nonce = provider_instance.get_authorization_url(
            state=state,
            nonce=nonce,
            prompt=prompt
        )
        
        # Store session data
        self._sessions[state] = {
            "provider": provider,
            "audience": audience,
            "nonce": nonce,
        }
        
        self.stats["logins_total"] += 1
        
        return authorization_url, state, nonce
    
    def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
        audience: str,
    ) -> str:
        """Handle OIDC callback and mint local JWT.
        
        Args:
            provider: Provider identifier
            code: Authorization code from provider
            state: OAuth state parameter
            audience: Target audience for JWT
        
        Returns:
            Local JWT token
        
        Raises:
            ValueError: If state is invalid or provider unknown
            AuthenticationError: If code exchange fails
        """
        # Validate state
        session = self._sessions.get(state)
        if not session:
            raise ValueError("Invalid or expired state")
        
        # Validate provider matches
        if session["provider"] != provider:
            raise ValueError("Provider mismatch")
        
        # Validate audience matches
        if session["audience"] != audience:
            raise ValueError("Audience mismatch")
        
        # Get provider instance
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        provider_instance = self.providers[provider]
        
        if not isinstance(provider_instance, OIDCProvider):
            raise ValueError(f"Provider {provider} does not support OIDC callback")
        
        try:
            # Exchange code for tokens
            token_response = provider_instance.exchange_code_for_token(code=code, state=state)
            
            # Get access token
            access_token = token_response.get("access_token")
            if not access_token:
                raise AuthenticationError("No access token in response")
            
            # Get user info
            user = provider_instance.get_user(access_token)
            if not user:
                raise AuthenticationError("Failed to retrieve user info")
            
            # Mint local JWT
            local_jwt = self.jwt_manager.mint_token(
                user=user,
                audience=audience,
                additional_claims={
                    "provider": provider,
                    "amr": ["pwd"],  # Authentication method: password (OIDC)
                }
            )
            
            # Clean up session
            del self._sessions[state]
            
            self.stats["tokens_minted"] += 1
            
            return local_jwt
        
        except Exception as e:
            logger.error(f"Callback handling failed: {e}")
            raise
    
    def validate_token(
        self,
        token: str,
        audience: str,
    ) -> Dict[str, Any]:
        """Validate a JWT token.
        
        Args:
            token: JWT token string
            audience: Expected audience
        
        Returns:
            Decoded token claims
        
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            claims = self.jwt_manager.validate_token(
                token=token,
                audience=audience,
                max_skew_seconds=self.config.security.max_skew_seconds
            )
            
            self.stats["tokens_validated"] += 1
            
            return claims
        
        except Exception as e:
            self.stats["validation_failures"] += 1
            raise
    
    def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS for public key distribution.
        
        Returns:
            JWKS dictionary
        """
        return self.jwt_manager.get_jwks()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.stats.copy()
