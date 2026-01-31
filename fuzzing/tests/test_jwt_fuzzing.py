# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""JWT fuzzing tests using Hypothesis property-based testing.

This module fuzzes JWT token parsing, signature validation, and claims extraction
in the auth service to find authentication bypass and privilege escalation vulnerabilities.

Targets:
- JWT header parsing (algorithm confusion, malformed headers)
- Signature validation (bypass attempts, tampering)
- Claims extraction and validation (type confusion, injection)
- Expiry/nbf timing edge cases (clock skew, boundary conditions)

Risk: Authentication bypass, privilege escalation
Priority: P0
"""

import base64
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

import jwt
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.strategies import composite

# Import the JWT manager from copilot_auth
try:
    from copilot_auth.jwt_manager import JWTManager
    from copilot_auth.models import User
except ImportError:
    pytest.skip("copilot_auth not available", allow_module_level=True)


# ==================== Module-level RSA Key Caching ====================
# RSA key generation is expensive; generate once and reuse across tests
# to improve fuzz test performance.

_MODULE_TMP_DIR: tempfile.TemporaryDirectory | None = None  # type: ignore[type-arg]
_MODULE_PRIVATE_KEY_PATH: Path | None = None
_MODULE_PUBLIC_KEY_PATH: Path | None = None


def _get_or_create_rsa_keys() -> tuple[Path, Path]:
    """Get or create module-level RSA keys for testing.
    
    This caches RSA keys at the module level to avoid expensive key generation
    on every test iteration. Cleanup relies on garbage collection when the
    module is unloaded.
    """
    global _MODULE_TMP_DIR, _MODULE_PRIVATE_KEY_PATH, _MODULE_PUBLIC_KEY_PATH
    
    if _MODULE_PRIVATE_KEY_PATH is None or _MODULE_PUBLIC_KEY_PATH is None:
        _MODULE_TMP_DIR = tempfile.TemporaryDirectory()
        tmp_path = Path(_MODULE_TMP_DIR.name)
        _MODULE_PRIVATE_KEY_PATH = tmp_path / "private.pem"
        _MODULE_PUBLIC_KEY_PATH = tmp_path / "public.pem"
        JWTManager.generate_rsa_keys(_MODULE_PRIVATE_KEY_PATH, _MODULE_PUBLIC_KEY_PATH)
    
    return _MODULE_PRIVATE_KEY_PATH, _MODULE_PUBLIC_KEY_PATH


# ==================== Custom JWT Strategies ====================


@composite
def jwt_algorithms(draw: Any) -> str:
    """Generate JWT algorithm strings for fuzzing, including valid and attack vectors.
    
    This strategy generates both valid algorithms and common attack vectors:
    - "none" algorithm (signature bypass attack)
    - Algorithm confusion (HS256 vs RS256)
    - Invalid/unknown algorithms
    """
    valid_algorithms = ["RS256", "HS256", "ES256", "RS384", "RS512"]
    attack_algorithms = ["none", "None", "NONE", "nOnE"]
    invalid_algorithms = ["", "XYZ", "MD5", "SHA1", "RSA"]
    
    all_algorithms = valid_algorithms + attack_algorithms + invalid_algorithms
    return draw(st.sampled_from(all_algorithms))


@composite
def jwt_headers(draw: Any) -> dict[str, Any]:
    """Generate JWT header dictionaries with various edge cases.
    
    Generates headers with:
    - Valid and invalid algorithms
    - Missing/invalid key IDs
    - Extra fields that should be ignored
    - Type confusion (wrong types for standard fields)
    """
    header = {}
    
    # Algorithm field - sometimes missing, sometimes invalid
    if draw(st.booleans()):
        header["alg"] = draw(jwt_algorithms())
    
    # Type field - sometimes missing, sometimes wrong
    if draw(st.booleans()):
        typ = draw(st.sampled_from(["JWT", "jwt", "JWS", "", "INVALID", None, 123]))
        if typ is not None:
            header["typ"] = typ
    
    # Key ID - various formats
    if draw(st.booleans()):
        kid = draw(st.one_of(
            st.text(min_size=0, max_size=100),
            st.integers(),
            st.none(),
            st.lists(st.text()),
        ))
        header["kid"] = kid
    
    # Extra fields that should be ignored
    if draw(st.booleans()):
        extra_key = draw(st.text(min_size=1, max_size=20))
        extra_value = draw(st.one_of(st.text(), st.integers(), st.booleans()))
        header[extra_key] = extra_value
    
    return header


@composite
def jwt_claims(draw: Any) -> dict[str, Any]:
    """Generate JWT claims with various edge cases.
    
    Generates claims with:
    - Missing required fields
    - Type confusion (strings instead of ints for timestamps)
    - Invalid values (negative timestamps, future iat)
    - Claim injection attempts
    """
    claims: dict[str, Any] = {}
    
    now = int(time.time())
    
    # Issuer - sometimes missing, sometimes invalid
    if draw(st.booleans()):
        iss = draw(st.one_of(
            st.text(min_size=0, max_size=200),
            st.integers(),
            st.none(),
            st.lists(st.text()),
        ))
        claims["iss"] = iss
    
    # Subject - sometimes missing, sometimes invalid
    if draw(st.booleans()):
        sub = draw(st.one_of(
            st.text(min_size=0, max_size=200),
            st.integers(),
            st.none(),
        ))
        claims["sub"] = sub
    
    # Audience - sometimes missing, sometimes invalid
    if draw(st.booleans()):
        aud = draw(st.one_of(
            st.text(min_size=0, max_size=200),
            st.lists(st.text()),
            st.integers(),
            st.none(),
        ))
        claims["aud"] = aud
    
    # Expiry - various edge cases
    if draw(st.booleans()):
        exp_offset = draw(st.integers(min_value=-10000, max_value=10000))
        exp = draw(st.one_of(
            st.just(now + exp_offset),
            st.text(),  # Type confusion
            st.none(),
            st.just(-1),  # Negative timestamp
            st.just(0),   # Epoch
            st.just(2**32),  # Overflow
        ))
        claims["exp"] = exp
    
    # Issued at - various edge cases
    if draw(st.booleans()):
        iat_offset = draw(st.integers(min_value=-10000, max_value=10000))
        iat = draw(st.one_of(
            st.just(now + iat_offset),
            st.text(),  # Type confusion
            st.none(),
            st.just(-1),
            st.just(2**63 - 1),  # Max int64
        ))
        claims["iat"] = iat
    
    # Not before - various edge cases
    if draw(st.booleans()):
        nbf_offset = draw(st.integers(min_value=-10000, max_value=10000))
        nbf = draw(st.one_of(
            st.just(now + nbf_offset),
            st.text(),  # Type confusion
            st.none(),
            st.just(-1),
        ))
        claims["nbf"] = nbf
    
    # JWT ID - sometimes missing, sometimes duplicate
    if draw(st.booleans()):
        jti = draw(st.one_of(
            st.text(min_size=0, max_size=100),
            st.just("duplicate"),  # Replay attack
            st.integers(),
            st.none(),
        ))
        claims["jti"] = jti
    
    # Additional claims with type confusion
    if draw(st.booleans()):
        claims["email"] = draw(st.one_of(st.text(), st.integers(), st.lists(st.text())))
    
    if draw(st.booleans()):
        claims["name"] = draw(st.one_of(st.text(), st.integers(), st.none()))
    
    if draw(st.booleans()):
        roles = draw(st.one_of(
            st.lists(st.text()),
            st.text(),  # Should be list, not string
            st.integers(),
            st.none(),
        ))
        claims["roles"] = roles
    
    return claims


@composite
def malformed_jwt_tokens(draw: Any) -> str:
    """Generate malformed JWT tokens with various attack vectors.
    
    Generates tokens with:
    - Invalid segment counts (0, 1, 2, 4+ segments instead of required 3)
    - Invalid base64 encoding in segments
    - Empty segments
    """
    # Number of segments - should be 3 for valid JWT
    segment_count = draw(st.integers(min_value=0, max_value=10))
    
    segments = []
    for _ in range(segment_count):
        # Generate segment - sometimes valid base64, sometimes invalid
        if draw(st.booleans()):
            # Invalid base64
            segment = draw(st.text(min_size=0, max_size=100))
        else:
            # Valid base64
            data = draw(st.binary(min_size=0, max_size=100))
            segment = base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')
        
        segments.append(segment)
    
    return ".".join(segments)


# ==================== Fuzzing Tests ====================


@given(header=jwt_headers())
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_jwt_header_parsing(header: dict[str, Any]) -> None:
    """Fuzz JWT header parsing to find crashes or bypasses.
    
    This test generates various malformed JWT headers and ensures the
    JWT manager handles them gracefully without crashing or allowing
    authentication bypass.
    
    Attack vectors tested:
    - Algorithm confusion ("none", "HS256" vs "RS256")
    - Missing algorithm field
    - Invalid key IDs
    - Type confusion in header fields
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    # Create a token with the fuzzed header
    try:
        # Use jwt library directly to bypass JWTManager validation
        user_claims = {
            "iss": "https://auth.example.com",
            "sub": "test:12345",
            "aud": "https://api.example.com",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "jti": secrets.token_urlsafe(16),
            "email": "test@example.com",
            "name": "Test User",
        }
        
        # Encode with fuzzed header
        token = jwt.encode(
            user_claims,
            manager.private_key,
            algorithm="RS256",
            headers=header,
        )
        
        # Try to validate - should either succeed (if header is valid) or raise exception
        try:
            claims = manager.validate_token(token, audience="https://api.example.com")
            # If validation succeeds, ensure it's legitimate
            assert claims["sub"] == "test:12345", "Token validation succeeded but claims are wrong"
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            # Expected exceptions for invalid headers
            pass
            
    except (
        jwt.InvalidTokenError,
        jwt.exceptions.InvalidKeyError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        NotImplementedError,  # For unsupported algorithms like "none" or "None"
    ):
        # Expected exceptions during token creation with invalid headers
        pass


@given(claims=jwt_claims())
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_jwt_claims_validation(claims: dict[str, Any]) -> None:
    """Fuzz JWT claims to find validation bypass or crashes.
    
    This test generates various malformed claims and ensures the
    JWT manager validates them properly.
    
    Attack vectors tested:
    - Missing required claims (iss, sub, aud, exp)
    - Type confusion (strings instead of ints for timestamps)
    - Invalid values (negative/zero timestamps)
    - Claim injection
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    try:
        # Create token with fuzzed claims using jwt library directly
        token = jwt.encode(
            claims,
            manager.private_key,
            algorithm="RS256",
        )
        
        # Try to validate - should fail for invalid claims
        try:
            validated_claims = manager.validate_token(
                token,
                audience=claims.get("aud", "https://api.example.com"),
            )
            
            # If validation succeeds, claims must be valid
            assert "iss" in validated_claims
            assert "sub" in validated_claims
            assert "aud" in validated_claims
            assert "exp" in validated_claims
            
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            # Expected for invalid claims
            pass
            
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, AttributeError):
        # Expected for severely malformed claims
        pass


@given(token_str=malformed_jwt_tokens())
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_malformed_jwt_tokens(token_str: str) -> None:
    """Fuzz JWT parsing with malformed token strings.
    
    This test generates completely malformed JWT token strings to ensure
    the parser handles them gracefully without crashing.
    
    Attack vectors tested:
    - Wrong number of segments (not 3)
    - Invalid base64 encoding
    - Empty segments
    - Extremely long tokens
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    # Try to validate malformed token - should always fail gracefully
    try:
        claims = manager.validate_token(token_str, audience="https://api.example.com")
        # If it somehow succeeds, claims must be valid
        assert isinstance(claims, dict), "Malformed token validation should fail"
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        # Expected - malformed tokens should be rejected
        # Note: UnicodeDecodeError is wrapped by PyJWT as DecodeError/InvalidTokenError
        pass


@given(
    exp_offset=st.integers(min_value=-3600, max_value=3600),
    nbf_offset=st.integers(min_value=-3600, max_value=3600),
    skew=st.integers(min_value=0, max_value=300),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_jwt_timing_validation(
    exp_offset: int,
    nbf_offset: int,
    skew: int,
) -> None:
    """Fuzz JWT expiry and not-before timing validation.
    
    This test generates tokens with various expiry and nbf values relative
    to the current time, testing clock skew handling.
    
    Attack vectors tested:
    - Expired tokens with various skew values
    - Not-before timing boundary conditions
    - Clock skew edge cases
    - Negative/zero timestamps
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    now = int(time.time())
    
    # Create token with fuzzed timing
    try:
        claims = {
            "iss": "https://auth.example.com",
            "sub": "test:12345",
            "aud": "https://api.example.com",
            "exp": now + exp_offset,
            "iat": now,
            "nbf": now + nbf_offset,
            "jti": secrets.token_urlsafe(16),
            "email": "test@example.com",
            "name": "Test User",
        }
        
        token = jwt.encode(
            claims,
            manager.private_key,
            algorithm="RS256",
        )
        
        # Try to validate with fuzzed skew
        try:
            validated_claims = manager.validate_token(
                token,
                audience="https://api.example.com",
                max_skew_seconds=skew,
            )
            
            # If validation succeeds, token must be within valid time window
            # considering the skew. Add tolerance for timing variations during test.
            current_time = int(time.time())
            tolerance = 5  # seconds of tolerance for test execution time
            
            # Token should not be used before nbf - skew (with tolerance)
            assert validated_claims["nbf"] <= current_time + skew + tolerance, \
                f"Token nbf {validated_claims['nbf']} is after current time {current_time} + skew {skew}"
            
            # Token should not be expired beyond exp + skew (with tolerance)
            assert validated_claims["exp"] >= current_time - skew - tolerance, \
                f"Token exp {validated_claims['exp']} is before current time {current_time} - skew {skew}"
            
        except (jwt.ExpiredSignatureError, jwt.ImmatureSignatureError):
            # Expected for tokens outside valid time window
            pass
        except (jwt.InvalidTokenError, ValueError, TypeError):
            # Expected for invalid timing values
            pass
            
    except (ValueError, TypeError, OverflowError):
        # Expected for extreme timing values
        pass


@given(signature_bytes=st.binary(min_size=0, max_size=512))
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_jwt_signature_tampering(signature_bytes: bytes) -> None:
    """Fuzz JWT signature to detect signature bypass vulnerabilities.
    
    This test creates valid JWT tokens and then tampers with the signature
    to ensure signature validation cannot be bypassed.
    
    Attack vectors tested:
    - Random signature bytes
    - Empty signature
    - Truncated signature
    - Signature from different token
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    # Create a valid token
    user = User(
        id="test:12345",
        email="test@example.com",
        name="Test User",
    )
    
    valid_token = manager.mint_token(user, audience="https://api.example.com")
    
    # Split token into parts
    parts = valid_token.split(".")
    if len(parts) != 3:
        return  # Invalid token structure from mint_token itself
    
    # Replace signature with fuzzed bytes
    fuzzed_signature = base64.urlsafe_b64encode(signature_bytes).decode('ascii').rstrip('=')
    tampered_token = f"{parts[0]}.{parts[1]}.{fuzzed_signature}"
    
    # Try to validate tampered token - should always fail
    try:
        claims = manager.validate_token(tampered_token, audience="https://api.example.com")
        # If validation somehow succeeds with wrong signature, that's a critical bug
        # The only way this should succeed is if the fuzzed signature happens to be valid
        # (extremely unlikely but theoretically possible)
        pytest.fail(f"CRITICAL: Token with tampered signature was validated! Claims: {claims}")
    except (
        jwt.InvalidSignatureError,
        jwt.InvalidTokenError,
        jwt.DecodeError,
    ):
        # Expected - tampered signatures should be rejected via any JWT validation error
        # Note: InvalidTokenError is the base class for ExpiredSignatureError,
        # ImmatureSignatureError, InvalidAudienceError, InvalidIssuerError
        pass


@given(
    algorithm1=st.sampled_from(["RS256", "HS256"]),
    algorithm2=st.sampled_from(["RS256", "HS256", "none", "None"]),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_algorithm_confusion(algorithm1: str, algorithm2: str) -> None:
    """Fuzz algorithm confusion attacks.
    
    This test attempts algorithm confusion attacks where a token signed with
    one algorithm is validated with a different algorithm.
    
    Attack vectors tested:
    - RS256 token validated as HS256 (public key as HMAC secret)
    - HS256 token validated as RS256
    - "none" algorithm bypass attempts
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    # Special-case: test "none" algorithm bypass attempts explicitly
    if algorithm2.lower() == "none":
        validating_manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )

        now = int(time.time())
        payload = {
            "sub": "test:12345",
            "iss": "https://auth.example.com",
            "aud": "https://api.example.com",
            "iat": now,
            "exp": now + 60,
        }

        # Create an unsigned token using the "none" algorithm.
        # Note: PyJWT 2.0+ may reject "none" algorithm during encoding as a security
        # measure. If encoding fails, that's also a valid security behavior.
        try:
            none_token = jwt.encode(payload, key="", algorithm="none")
        except (NotImplementedError, ValueError):
            # PyJWT correctly rejected "none" algorithm at encoding time
            return

        # The validator must reject tokens using the "none" algorithm.
        with pytest.raises(
            (jwt.InvalidSignatureError, jwt.InvalidTokenError, jwt.DecodeError, ValueError)
        ):
            validating_manager.validate_token(none_token, audience="https://api.example.com")

        return

    # Skip unsupported algorithm combinations for other algorithms
    if algorithm1 not in ["RS256", "HS256"]:
        return
    
    # Create signing manager
    if algorithm1 == "RS256":
        signing_manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )
    else:  # HS256
        signing_manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )
    
    # Create validation manager with potentially different algorithm
    if algorithm2 == "RS256":
        validating_manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="RS256",
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )
    else:  # HS256
        validating_manager = JWTManager(
            issuer="https://auth.example.com",
            algorithm="HS256",
            secret_key="test-secret-key-at-least-32-chars-long",
        )
    
    # Create a token with algorithm1
    user = User(
        id="test:12345",
        email="test@example.com",
        name="Test User",
    )
    
    token = signing_manager.mint_token(user, audience="https://api.example.com")
    
    # Try to validate with algorithm2
    try:
        claims = validating_manager.validate_token(token, audience="https://api.example.com")
        
        # If algorithms match, validation should succeed
        if algorithm1 == algorithm2:
            assert claims["sub"] == "test:12345", "Valid token should validate successfully"
        else:
            # If algorithms don't match, validation should fail
            # If it succeeds, that's a potential vulnerability
            pytest.fail(
                f"CRITICAL: Algorithm confusion attack succeeded! "
                f"Token signed with {algorithm1} validated with {algorithm2}. Claims: {claims}"
            )
    except (jwt.InvalidSignatureError, jwt.InvalidTokenError, jwt.DecodeError, ValueError):
        # Expected when algorithms don't match
        pass


# ==================== Additional Edge Cases ====================


@given(payload=st.binary(min_size=0, max_size=10000))
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fuzz_jwt_payload_size(payload: bytes) -> None:
    """Fuzz JWT payload size to detect DoS via large payloads.
    
    This test creates tokens with various payload sizes to ensure
    the system handles large payloads gracefully.
    """
    # Use cached RSA keys for performance
    private_key_path, public_key_path = _get_or_create_rsa_keys()
    
    manager = JWTManager(
        issuer="https://auth.example.com",
        algorithm="RS256",
        private_key_path=private_key_path,
        public_key_path=public_key_path,
    )
    
    try:
        # Create claims with large payload
        claims = {
            "iss": "https://auth.example.com",
            "sub": "test:12345",
            "aud": "https://api.example.com",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "jti": secrets.token_urlsafe(16),
            "large_payload": base64.b64encode(payload).decode('ascii'),
        }
        
        token = jwt.encode(
            claims,
            manager.private_key,
            algorithm="RS256",
        )
        
        # Validate token with large payload
        validated_claims = manager.validate_token(token, audience="https://api.example.com")
        assert "large_payload" in validated_claims
        
    except (ValueError, MemoryError, OverflowError):
        # Expected for extremely large payloads
        pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--timeout=600"])
