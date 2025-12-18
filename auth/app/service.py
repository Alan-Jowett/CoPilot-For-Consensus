# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service implementation."""

import asyncio
import secrets
import time
from typing import Any, Dict, Optional

from copilot_auth import (
    create_identity_provider,
    IdentityProvider,
    JWTManager,
    OIDCProvider,
    AuthenticationError,
)
from copilot_logging import create_logger

from .config import load_auth_config

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
    
    def __init__(self, config):
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
        self._sessions_lock = asyncio.Lock()  # Protect concurrent access
        self._session_ttl_seconds = 600  # 10 minutes
        self._last_cleanup_time = time.time()
        self._cleanup_interval_seconds = 60  # Clean up every minute
        
        # Initialize providers and JWT manager
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize OIDC providers and JWT manager."""
        logger.info("Initializing Auth Service...")
        
        # Initialize JWT manager
        # Get key paths from processed config (added dynamically in load_auth_config)
        private_key_path = getattr(self.config._config, '_jwt_private_key_path', None)
        public_key_path = getattr(self.config._config, '_jwt_public_key_path', None)
        
        self.jwt_manager = JWTManager(
            issuer=self.config.issuer,
            algorithm=self.config.jwt_algorithm,
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            secret_key=getattr(self.config, 'jwt_secret_key', None),
            key_id=self.config.jwt_key_id,
            default_expiry=self.config.jwt_default_expiry,
        )
        
        # Initialize OIDC providers from config
        self._initialize_providers()
        
        logger.info(f"Auth Service initialized with {len(self.providers)} providers")
    
    def _initialize_providers(self) -> None:
        """Initialize OIDC providers from configuration."""
        # GitHub provider
        if hasattr(self.config, 'github_client_id') and self.config.github_client_id:
            try:
                redirect_uri = getattr(self.config, 'github_redirect_uri', None) or f"{self.config.issuer}/callback"
                provider = create_identity_provider(
                    provider_type="github",
                    client_id=self.config.github_client_id,
                    client_secret=self.config.github_client_secret,
                    redirect_uri=redirect_uri,
                    api_base_url=getattr(self.config, 'github_api_base_url', None),
                )
                if isinstance(provider, OIDCProvider):
                    provider.discover()
                self.providers['github'] = provider
                logger.info("Initialized provider: github")
            except Exception as e:
                logger.error(f"Failed to initialize GitHub provider: {e}")
        
        # Google provider
        if hasattr(self.config, 'google_client_id') and self.config.google_client_id:
            try:
                redirect_uri = getattr(self.config, 'google_redirect_uri', None) or f"{self.config.issuer}/callback"
                provider = create_identity_provider(
                    provider_type="google",
                    client_id=self.config.google_client_id,
                    client_secret=self.config.google_client_secret,
                    redirect_uri=redirect_uri,
                )
                if isinstance(provider, OIDCProvider):
                    provider.discover()
                self.providers['google'] = provider
                logger.info("Initialized provider: google")
            except Exception as e:
                logger.error(f"Failed to initialize Google provider: {e}")
        
        # Microsoft provider
        if hasattr(self.config, 'microsoft_client_id') and self.config.microsoft_client_id:
            try:
                redirect_uri = getattr(self.config, 'microsoft_redirect_uri', None) or f"{self.config.issuer}/callback"
                provider = create_identity_provider(
                    provider_type="microsoft",
                    client_id=self.config.microsoft_client_id,
                    client_secret=self.config.microsoft_client_secret,
                    redirect_uri=redirect_uri,
                    tenant=getattr(self.config, 'microsoft_tenant', 'common'),
                )
                if isinstance(provider, OIDCProvider):
                    provider.discover()
                self.providers['microsoft'] = provider
                logger.info("Initialized provider: microsoft")
            except Exception as e:
                logger.error(f"Failed to initialize Microsoft provider: {e}")
    
    def is_ready(self) -> bool:
        """Check if service is ready to handle requests."""
        return self.jwt_manager is not None and len(self.providers) > 0
    
    async def initiate_login(
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
        
        # Generate state, nonce, and PKCE verifier/challenge
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier, code_challenge = provider_instance.build_pkce_pair()
        
        # Get authorization URL
        authorization_url, state, nonce = provider_instance.get_authorization_url(
            state=state,
            nonce=nonce,
            prompt=prompt,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        
        # Store session data (thread-safe)
        async with self._sessions_lock:
            self._sessions[state] = {
                "provider": provider,
                "audience": audience,
                "nonce": nonce,
                "code_verifier": code_verifier,
                "created_at": time.time(),
            }
            
            # Opportunistically clean up expired sessions
            self._cleanup_expired_sessions()
        
        self.stats["logins_total"] += 1
        
        return authorization_url, state, nonce
    
    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> str:
        """Handle OIDC callback and mint local JWT.
        
        Args:
            code: Authorization code from provider
            state: OAuth state parameter
        
        Returns:
            Local JWT token
        
        Raises:
            ValueError: If state is invalid or provider unknown
            AuthenticationError: If code exchange fails
        """
        # Retrieve session data (thread-safe)
        async with self._sessions_lock:
            session = self._sessions.get(state)
            if not session:
                raise ValueError("Invalid or expired state")
            
            # Check if session has expired
            session_age = time.time() - session.get("created_at", 0)
            if session_age > self._session_ttl_seconds:
                del self._sessions[state]
                raise ValueError(f"Session expired (age: {session_age:.0f}s, TTL: {self._session_ttl_seconds}s)")

            provider = session["provider"]
            audience = session["audience"]
            nonce = session.get("nonce")
            code_verifier = session.get("code_verifier")
        
        # Get provider instance
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        provider_instance = self.providers[provider]
        
        if not isinstance(provider_instance, OIDCProvider):
            raise ValueError(f"Provider {provider} does not support OIDC callback")
        
        try:
            # Exchange code for tokens
            token_response = provider_instance.exchange_code_for_token(
                code=code,
                code_verifier=code_verifier,
            )

            # Require ID token and validate it (iss/aud/nonce/signature)
            id_token = token_response.get("id_token")
            if not id_token:
                raise AuthenticationError("No id_token in response")

            provider_instance.validate_id_token(id_token=id_token, nonce=nonce)
            
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
            
            # Clean up session (thread-safe)
            async with self._sessions_lock:
                del self._sessions[state]
            
            self.stats["tokens_minted"] += 1
            
            return local_jwt
        
        except Exception as e:
            logger.error(f"Callback handling failed: {e}")
            raise
        finally:
            # Ensure session is not reusable (thread-safe)
            async with self._sessions_lock:
                self._sessions.pop(state, None)
    
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
    
    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions (called with lock held).
        
        This is a lazy cleanup mechanism that runs periodically when
        new sessions are created. For production, use Redis with TTL.
        """
        # Only clean up if interval has elapsed
        now = time.time()
        if now - self._last_cleanup_time < self._cleanup_interval_seconds:
            return
        
        self._last_cleanup_time = now
        
        # Find and remove expired sessions
        expired_states = [
            state for state, session in self._sessions.items()
            if now - session.get("created_at", 0) > self._session_ttl_seconds
        ]
        
        for state in expired_states:
            del self._sessions[state]
        
        if expired_states:
            logger.info(f"Cleaned up {len(expired_states)} expired sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()
        stats["active_sessions"] = len(self._sessions)
        return stats
