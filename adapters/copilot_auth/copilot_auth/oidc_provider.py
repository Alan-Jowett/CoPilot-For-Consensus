# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OIDC base provider with common OIDC authentication flow logic.

This module provides a base class for OIDC-based identity providers,
implementing the common authentication code exchange and discovery logic.
"""

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional
from abc import abstractmethod

import httpx
import jwt

from .provider import IdentityProvider, AuthenticationError, ProviderError
from .models import User


class OIDCProvider(IdentityProvider):
    """Base class for OIDC identity providers.
    
    Provides common OIDC functionality including:
    - Discovery endpoint parsing
    - Authorization URL generation
    - Token exchange via authorization code
    - ID token validation
    
    Attributes:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        redirect_uri: Callback URL for OAuth flow
        discovery_url: OIDC discovery endpoint URL
        scopes: OAuth scopes to request
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        discovery_url: str,
        scopes: Optional[list[str]] = None,
    ):
        """Initialize the OIDC provider.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Callback URL for OAuth flow
            discovery_url: OIDC discovery endpoint URL
            scopes: OAuth scopes to request (default: ["openid", "profile", "email"])
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.discovery_url = discovery_url
        self.scopes = scopes or ["openid", "profile", "email"]
        
        # Will be populated by discover()
        self._discovery_data: Optional[Dict[str, Any]] = None
        self._authorization_endpoint: Optional[str] = None
        self._token_endpoint: Optional[str] = None
        self._userinfo_endpoint: Optional[str] = None
        self._jwks_uri: Optional[str] = None
        self._issuer: Optional[str] = None
        self._jwks_cache: Optional[Dict[str, Any]] = None
    
    def discover(self) -> None:
        """Perform OIDC discovery to retrieve provider endpoints.
        
        Raises:
            ProviderError: If discovery fails or required endpoints are missing
        """
        try:
            response = httpx.get(self.discovery_url, timeout=10.0)
            response.raise_for_status()
            self._discovery_data = response.json()
            
            # Extract required endpoints
            self._authorization_endpoint = self._discovery_data.get("authorization_endpoint")
            self._token_endpoint = self._discovery_data.get("token_endpoint")
            self._userinfo_endpoint = self._discovery_data.get("userinfo_endpoint")
            self._jwks_uri = self._discovery_data.get("jwks_uri")
            self._issuer = self._discovery_data.get("issuer")
            
            if not all([self._authorization_endpoint, self._token_endpoint]):
                raise ProviderError(
                    "OIDC discovery response missing required endpoints "
                    "(authorization_endpoint, token_endpoint)"
                )
        
        except httpx.HTTPError as e:
            raise ProviderError(f"OIDC discovery failed: {e}") from e
    
    def get_authorization_url(
        self,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        prompt: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> tuple[str, str, str]:
        """Generate authorization URL for OAuth flow.
        
        Args:
            state: OAuth state parameter (generated if not provided)
            nonce: OIDC nonce parameter (generated if not provided)
            prompt: OAuth prompt parameter (e.g., "consent", "select_account")
        
        Returns:
            Tuple of (authorization_url, state, nonce)
        
        Raises:
            ProviderError: If discovery has not been performed
        """
        if not self._authorization_endpoint:
            self.discover()
        
        # Generate state and nonce if not provided
        state = state or secrets.token_urlsafe(32)
        nonce = nonce or secrets.token_urlsafe(32)
        
        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
        }

        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        
        if prompt:
            params["prompt"] = prompt
        
        # Construct URL with query parameters
        query_string = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        authorization_url = f"{self._authorization_endpoint}?{query_string}"
        
        return authorization_url, state, nonce
    
    def exchange_code_for_token(
        self,
        code: str,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange authorization code for access and ID tokens.
        
        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier (optional)
        
        Returns:
            Token response containing access_token, id_token, etc.
        
        Raises:
            AuthenticationError: If code exchange fails
            ProviderError: If token endpoint is unavailable
        """
        if not self._token_endpoint:
            self.discover()
        
        try:
            response = httpx.post(
                self._token_endpoint,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code": code,
                    **({"code_verifier": code_verifier} if code_verifier else {}),
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(f"Token exchange failed: {e}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Token endpoint unavailable: {e}") from e
    
    def get_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Retrieve user information from userinfo endpoint.
        
        Args:
            access_token: OAuth access token
        
        Returns:
            User information from provider
        
        Raises:
            AuthenticationError: If access token is invalid
            ProviderError: If userinfo endpoint is unavailable
        """
        if not self._userinfo_endpoint:
            self.discover()
        
        try:
            response = httpx.get(
                self._userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(f"Failed to retrieve user info: {e}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Userinfo endpoint unavailable: {e}") from e
    
    @abstractmethod
    def _map_userinfo_to_user(self, userinfo: Dict[str, Any], provider_id: str) -> User:
        """Map provider-specific userinfo to User model.
        
        Args:
            userinfo: Raw userinfo from provider
            provider_id: Provider identifier (e.g., "github", "google")
        
        Returns:
            User object with mapped fields
        """
        pass
    
    def get_user(self, token: str) -> Optional[User]:
        """Retrieve user information from an OAuth access token.
        
        This method uses the access token to fetch user info from the
        provider's userinfo endpoint and maps it to a User object.
        
        Args:
            token: OAuth access token
        
        Returns:
            User object if token is valid, None otherwise
        
        Raises:
            AuthenticationError: If token is invalid
            ProviderError: If provider service is unavailable
        """
        userinfo = self.get_userinfo(token)
        return self._map_userinfo_to_user(userinfo, self.__class__.__name__.replace("IdentityProvider", "").lower())

    def validate_id_token(self, id_token: str, nonce: str, leeway: int = 60) -> Dict[str, Any]:
        """Validate ID token using provider JWKS.

        Args:
            id_token: Raw ID token
            nonce: Expected nonce value
            leeway: Clock skew tolerance

        Returns:
            Decoded and validated ID token claims
        """
        if not self._jwks_uri:
            self.discover()

        if not self._jwks_cache:
            try:
                jwks_resp = httpx.get(self._jwks_uri, timeout=10.0)
                jwks_resp.raise_for_status()
                self._jwks_cache = jwks_resp.json()
            except httpx.HTTPError as e:
                raise ProviderError(f"Failed to fetch JWKS: {e}") from e

        # Use PyJWT to verify signature and standard claims
        try:
            decoded = jwt.decode(
                id_token,
                key=self._jwks_cache,
                algorithms=["RS256", "HS256"],
                audience=self.client_id,
                issuer=self._issuer,
                leeway=leeway,
                options={"verify_aud": True, "verify_iss": bool(self._issuer)},
            )
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid ID token: {e}") from e

        # Nonce check (OIDC CSRF protection)
        token_nonce = decoded.get("nonce")
        if nonce and token_nonce != nonce:
            raise AuthenticationError("ID token nonce mismatch")

        return decoded

    @staticmethod
    def build_pkce_pair() -> tuple[str, str]:
        """Generate code_verifier and code_challenge (S256)."""
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return verifier, challenge
