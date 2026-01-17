# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service implementation."""

import asyncio
from dataclasses import asdict
from dataclasses import replace
import secrets
import time
from pathlib import Path
from typing import Any, Protocol, cast

from copilot_auth import AuthenticationError, JWTManager, create_identity_provider
from copilot_config.generated.adapters.oidc_providers import AdapterConfig_OidcProviders
from copilot_config.generated.services.auth import ServiceConfig_Auth
from copilot_logging import get_logger

from . import OAUTH_PROVIDERS, SUPPORTED_PROVIDERS
from .role_store import RoleStore

logger = get_logger(__name__)


class _OidcProvider(Protocol):
    def discover(self) -> None: ...

    @staticmethod
    def build_pkce_pair() -> tuple[str, str]: ...

    def get_authorization_url(
        self,
        state: str | None = None,
        nonce: str | None = None,
        prompt: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> tuple[str, str, str]: ...

    def exchange_code_for_token(self, code: str, code_verifier: str | None = None) -> dict[str, Any]: ...

    def validate_and_get_user(self, token_response: dict, nonce: str | None = None) -> Any: ...


def create_identity_providers(
    config: AdapterConfig_OidcProviders,
    *,
    issuer: str | None = None,
) -> dict[str, _OidcProvider]:
    """Create identity providers from the typed oidc_providers adapter config.

    Implemented here (instead of importing copilot_auth.factory.create_identity_providers)
    so that unit tests can patch `app.service.create_identity_provider`.
    """
    composite = config.oidc_providers
    if composite is None:
        return {}

    default_redirect_uri = f"{issuer.rstrip('/')}/callback" if issuer else None

    def _with_default_redirect_uri(provider_config: Any, field_name: str) -> Any:
        if default_redirect_uri and getattr(provider_config, field_name) is None:
            return replace(provider_config, **{field_name: default_redirect_uri})
        return provider_config

    providers: dict[str, _OidcProvider] = {}
    github = composite.github
    google = composite.google
    microsoft = composite.microsoft

    if github is not None:
        try:
            github = _with_default_redirect_uri(github, "github_redirect_uri")
            assert github is not None  # Type narrowing: _with_default_redirect_uri preserves non-None
            provider = create_identity_provider(
                "github",
                github,
                issuer=issuer,
            )
            required_methods = (
                "build_pkce_pair",
                "get_authorization_url",
                "exchange_code_for_token",
                "validate_and_get_user",
            )
            if not all(callable(getattr(provider, m, None)) for m in required_methods):
                logger.error("Provider github does not support the OIDC flow")
            else:
                providers["github"] = cast(_OidcProvider, provider)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to initialize provider github: {e}")
    if google is not None:
        try:
            google = _with_default_redirect_uri(google, "google_redirect_uri")
            assert google is not None  # Type narrowing: _with_default_redirect_uri preserves non-None
            provider = create_identity_provider(
                "google",
                google,
                issuer=issuer,
            )
            required_methods = (
                "build_pkce_pair",
                "get_authorization_url",
                "exchange_code_for_token",
                "validate_and_get_user",
            )
            if not all(callable(getattr(provider, m, None)) for m in required_methods):
                logger.error("Provider google does not support the OIDC flow")
            else:
                providers["google"] = cast(_OidcProvider, provider)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to initialize provider google: {e}")
    if microsoft is not None:
        try:
            microsoft = _with_default_redirect_uri(microsoft, "microsoft_redirect_uri")
            assert microsoft is not None  # Type narrowing: _with_default_redirect_uri preserves non-None
            provider = create_identity_provider(
                "microsoft",
                microsoft,
                issuer=issuer,
            )
            required_methods = (
                "build_pkce_pair",
                "get_authorization_url",
                "exchange_code_for_token",
                "validate_and_get_user",
            )
            if not all(callable(getattr(provider, m, None)) for m in required_methods):
                logger.error("Provider microsoft does not support the OIDC flow")
            else:
                providers["microsoft"] = cast(_OidcProvider, provider)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to initialize provider microsoft: {e}")

    # Provider discovery (best-effort)
    for name, provider in list(providers.items()):
        provider: _OidcProvider  # Type annotation for loop variable
        discover = getattr(provider, "discover", None)
        if callable(discover):
            try:
                discover()
            except Exception as e:  # noqa: BLE001
                logger.error(f"Provider {name} discovery failed: {e}")
                providers.pop(name, None)

    return providers


class AuthService:
    """Authentication service for OIDC login and JWT minting.

    Coordinates multiple OIDC providers and issues local JWTs.

    Attributes:
        config: Auth service configuration
        providers: Dictionary of OIDC providers by name
        jwt_manager: JWT token manager
        stats: Service statistics
    """

    def __init__(self, config: ServiceConfig_Auth):
        """Initialize the auth service.

        Args:
            config: Auth service configuration
        """
        self.config = config
        self.providers: dict[str, _OidcProvider] = {}
        self.jwt_manager: JWTManager | None = None

        # Statistics
        self.stats = {
            "logins_total": 0,
            "tokens_minted": 0,
            "tokens_validated": 0,
            "validation_failures": 0,
        }

        # Session storage (for MVP, in-memory; production should use Redis)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._sessions_lock = asyncio.Lock()  # Protect concurrent access
        self._session_ttl_seconds = 600  # 10 minutes
        self._last_cleanup_time = time.time()
        self._cleanup_interval_seconds = 60  # Clean up every minute

        # Role store (backed by copilot_storage)
        self.role_store: RoleStore

        # Initialize providers and JWT manager
        self._initialize()

    def _initialize(self) -> None:
        """Initialize OIDC providers and JWT manager."""
        logger.info("Initializing Auth Service...")

        settings = self.config.service_settings

        algorithm = settings.jwt_algorithm or "RS256"

        private_key_path: Path | None
        public_key_path: Path | None

        if algorithm == "RS256":
            private_key = settings.jwt_private_key
            public_key = settings.jwt_public_key

            if private_key is None or public_key is None:
                raise ValueError(
                    "RS256 requires jwt_private_key and jwt_public_key to be configured"
                )

            # Write keys to temp files for JWTManager
            import tempfile

            temp_dir = Path(tempfile.gettempdir()) / "auth_keys"
            temp_dir.mkdir(exist_ok=True)

            private_key_path = temp_dir / "jwt_private.pem"
            public_key_path = temp_dir / "jwt_public.pem"

            private_key_path.write_text(private_key)
            public_key_path.write_text(public_key)

        elif algorithm.startswith("HS"):
            private_key_path = None
            public_key_path = None
            if settings.jwt_secret_key is None:
                raise ValueError(f"{algorithm} requires jwt_secret_key to be configured")

        else:
            private_key_path = None
            public_key_path = None

        default_expiry = settings.jwt_default_expiry if settings.jwt_default_expiry is not None else 1800

        self.jwt_manager = JWTManager(
            issuer=settings.issuer,
            algorithm=algorithm,
            private_key_path=private_key_path,
            public_key_path=public_key_path,
            secret_key=settings.jwt_secret_key,
            key_id=settings.jwt_key_id,
            default_expiry=default_expiry,
        )

        # Initialize role store
        self.role_store = RoleStore(self.config)

        # Initialize OIDC providers from config
        self.providers = create_identity_providers(self.config.oidc_providers, issuer=settings.issuer)

        # Ready
        logger.info(f"Auth Service initialized with {len(self.providers)} providers")


    def is_ready(self) -> bool:
        """Check if service is ready to handle requests."""
        return self.jwt_manager is not None and len(self.providers) > 0

    async def initiate_login(
        self,
        provider: str,
        audience: str,
        prompt: str | None = None,
    ) -> tuple[str, str, str]:
        """Initiate OIDC login flow.

        Args:
            provider: Provider identifier
            audience: Target audience for JWT
            prompt: Optional OAuth prompt parameter

        Returns:
            Tuple of (authorization_url, state, nonce)

        Raises:
            ValueError: If provider is unknown or not configured
        """
        if provider not in self.providers:
            configured_providers = list(self.providers.keys())
            configured_list = ", ".join(configured_providers) if configured_providers else "none"
            if provider in OAUTH_PROVIDERS:
                raise ValueError(
                    f"Provider '{provider}' is not configured. "
                    f"Please configure OAuth credentials for {provider}. "
                    f"See documentation for setup instructions. "
                    f"Currently configured providers: {configured_list}"
                )
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}. "
                f"Currently configured: {configured_list}"
            )

        provider_instance = self.providers[provider]

        # Avoid importing internal provider classes; validate capability via duck typing.
        required_methods = ("build_pkce_pair", "get_authorization_url")
        if not all(callable(getattr(provider_instance, m, None)) for m in required_methods):
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

        required_methods = ("exchange_code_for_token", "validate_and_get_user")
        if not all(callable(getattr(provider_instance, m, None)) for m in required_methods):
            raise ValueError(f"Provider {provider} does not support OIDC callback")

        try:
            # Exchange code for tokens
            token_response = provider_instance.exchange_code_for_token(
                code=code,
                code_verifier=code_verifier,
            )


            # GitHub OAuth does not return id_tokens; handle via access_token + userinfo
            id_token = token_response.get("id_token")

            # Get access token (required for all flows)
            access_token = token_response.get("access_token")
            if not access_token:
                raise AuthenticationError("No access token in response")

            # Use provider's validate_and_get_user to handle provider-specific logic
            user = provider_instance.validate_and_get_user(token_response, nonce=nonce)

            if not user:
                raise AuthenticationError("Failed to retrieve user info")

            settings = self.config.service_settings

            auto_roles = settings.auto_approve_roles or ""
            auto_roles_list = [r.strip() for r in auto_roles.split(",") if r.strip()]
            auto_enabled = bool(settings.auto_approve_enabled)
            first_user_promotion_enabled = bool(settings.first_user_auto_promotion_enabled)

            roles, status = self.role_store.get_roles_for_user(
                user=user,
                auto_approve_enabled=auto_enabled,
                auto_approve_roles=auto_roles_list,
                first_user_auto_promotion_enabled=first_user_promotion_enabled,
            )

            user.roles = roles
            pending = status != "approved"

            jwt_manager = self.jwt_manager
            if jwt_manager is None:
                raise RuntimeError("JWT manager is not initialized")

            # Mint local JWT
            local_jwt = jwt_manager.mint_token(
                user=user,
                audience=audience,
                additional_claims={
                    "provider": provider,
                    "amr": ["pwd"],  # Authentication method: password (OIDC)
                    "pending_access": pending,
                    "role_status": status,
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
    ) -> dict[str, Any]:
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
            jwt_manager = self.jwt_manager
            if jwt_manager is None:
                raise RuntimeError("JWT manager is not initialized")

            max_skew_seconds = (
                self.config.service_settings.max_skew_seconds
                if self.config.service_settings.max_skew_seconds is not None
                else 90
            )

            claims = jwt_manager.validate_token(
                token=token,
                audience=audience,
                max_skew_seconds=max_skew_seconds,
            )

            self.stats["tokens_validated"] += 1

            return claims

        except Exception:
            self.stats["validation_failures"] += 1
            raise

    def get_jwks(self) -> dict[str, Any]:
        """Get JWKS for public key distribution.

        Returns:
            JWKS dictionary
        """
        jwt_manager = self.jwt_manager
        if jwt_manager is None:
            raise RuntimeError("JWT manager is not initialized")

        return jwt_manager.get_jwks()

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

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()
        stats["active_sessions"] = len(self._sessions)
        return stats
