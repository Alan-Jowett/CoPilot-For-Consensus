# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Auth service configuration."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JWTConfig(BaseModel):
    """JWT configuration."""
    
    algorithm: str = Field(default="RS256", description="JWT signing algorithm (RS256 or HS256)")
    private_key_path: Optional[Path] = Field(default=None, description="Path to RSA private key (RS256)")
    public_key_path: Optional[Path] = Field(default=None, description="Path to RSA public key (RS256)")
    secret_key: Optional[str] = Field(default=None, description="HMAC secret (HS256)")
    key_id: str = Field(default="default", description="Key ID for rotation")
    default_expiry: int = Field(default=1800, description="Default token lifetime in seconds")
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class OIDCProviderConfig(BaseModel):
    """OIDC provider configuration."""
    
    provider_type: str = Field(..., description="Provider type (github, google, microsoft)")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    redirect_uri: str = Field(..., description="OAuth callback URL")
    api_base_url: Optional[str] = Field(default=None, description="API base URL (GitHub only)")
    tenant: Optional[str] = Field(default="common", description="Tenant ID (Microsoft only)")


class SecurityConfig(BaseModel):
    """Security configuration."""
    
    require_pkce: bool = Field(default=True, description="Require PKCE for OAuth")
    require_nonce: bool = Field(default=True, description="Require nonce for OIDC")
    max_skew_seconds: int = Field(default=90, description="Maximum clock skew tolerance")
    enable_dpop: bool = Field(default=False, description="Enable DPoP proof-of-possession")


class AuthConfig(BaseModel):
    """Auth service configuration."""
    
    issuer: str = Field(..., description="JWT issuer URL")
    audiences: list[str] = Field(default_factory=list, description="Allowed JWT audiences")
    jwt: JWTConfig = Field(default_factory=JWTConfig, description="JWT configuration")
    oidc_providers: Dict[str, OIDCProviderConfig] = Field(
        default_factory=dict,
        description="OIDC provider configurations"
    )
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")
    
    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Create configuration from environment variables.
        
        Returns:
            AuthConfig instance
        """
        # Load issuer
        issuer = os.getenv("AUTH_ISSUER", "http://localhost:8090")
        
        # Load audiences
        audiences_str = os.getenv("AUTH_AUDIENCES", "copilot-orchestrator")
        audiences = [a.strip() for a in audiences_str.split(",")]
        
        # Load JWT config
        jwt_algorithm = os.getenv("JWT_ALGORITHM", "RS256")
        jwt_key_id = os.getenv("JWT_KEY_ID", "default")
        jwt_expiry = int(os.getenv("JWT_DEFAULT_EXPIRY", "1800"))
        
        jwt_config = JWTConfig(
            algorithm=jwt_algorithm,
            key_id=jwt_key_id,
            default_expiry=jwt_expiry,
        )
        
        # Load keys based on algorithm
        if jwt_algorithm == "RS256":
            private_key_path = os.getenv("JWT_PRIVATE_KEY_PATH")
            public_key_path = os.getenv("JWT_PUBLIC_KEY_PATH")
            
            if not private_key_path or not public_key_path:
                # Use default dev keys
                base_path = Path(__file__).parent.parent / "config"
                private_key_path = str(base_path / "dev_jwt_private.pem")
                public_key_path = str(base_path / "dev_jwt_public.pem")
            
            jwt_config.private_key_path = Path(private_key_path)
            jwt_config.public_key_path = Path(public_key_path)
        
        elif jwt_algorithm == "HS256":
            secret_key = os.getenv("JWT_SECRET_KEY")
            if not secret_key:
                raise ValueError("JWT_SECRET_KEY required for HS256 algorithm")
            
            jwt_config.secret_key = secret_key
        
        # Load OIDC providers
        oidc_providers: Dict[str, OIDCProviderConfig] = {}
        
        # GitHub
        github_client_id = os.getenv("AUTH_GITHUB_CLIENT_ID")
        github_client_secret = os.getenv("AUTH_GITHUB_CLIENT_SECRET")
        if github_client_id and github_client_secret:
            oidc_providers["github"] = OIDCProviderConfig(
                provider_type="github",
                client_id=github_client_id,
                client_secret=github_client_secret,
                redirect_uri=os.getenv("AUTH_GITHUB_REDIRECT_URI", f"{issuer}/callback"),
                api_base_url=os.getenv("AUTH_GITHUB_API_BASE_URL", "https://api.github.com"),
            )
        
        # Google
        google_client_id = os.getenv("AUTH_GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("AUTH_GOOGLE_CLIENT_SECRET")
        if google_client_id and google_client_secret:
            oidc_providers["google"] = OIDCProviderConfig(
                provider_type="google",
                client_id=google_client_id,
                client_secret=google_client_secret,
                redirect_uri=os.getenv("AUTH_GOOGLE_REDIRECT_URI", f"{issuer}/callback"),
            )
        
        # Microsoft
        ms_client_id = os.getenv("AUTH_MS_CLIENT_ID")
        ms_client_secret = os.getenv("AUTH_MS_CLIENT_SECRET")
        if ms_client_id and ms_client_secret:
            oidc_providers["microsoft"] = OIDCProviderConfig(
                provider_type="microsoft",
                client_id=ms_client_id,
                client_secret=ms_client_secret,
                redirect_uri=os.getenv("AUTH_MS_REDIRECT_URI", f"{issuer}/callback"),
                tenant=os.getenv("AUTH_MS_TENANT", "common"),
            )
        
        # Load security config
        security = SecurityConfig(
            require_pkce=os.getenv("AUTH_REQUIRE_PKCE", "true").lower() == "true",
            require_nonce=os.getenv("AUTH_REQUIRE_NONCE", "true").lower() == "true",
            max_skew_seconds=int(os.getenv("AUTH_MAX_SKEW_SECONDS", "90")),
            enable_dpop=os.getenv("AUTH_ENABLE_DPOP", "false").lower() == "true",
        )
        
        return cls(
            issuer=issuer,
            audiences=audiences,
            jwt=jwt_config,
            oidc_providers=oidc_providers,
            security=security,
        )
