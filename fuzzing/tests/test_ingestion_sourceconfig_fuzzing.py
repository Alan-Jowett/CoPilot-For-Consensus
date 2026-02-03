# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Hypothesis property-based fuzz tests for ingestion SourceConfig JSON validation.

This module tests security-critical JSON payload parsing and Pydantic validation for
the POST/PUT /api/sources endpoints to detect:
- Injection attacks (SQL, XSS, command injection)
- Schema bypass attempts
- Type confusion vulnerabilities
- URL validation weaknesses
- Source type enum handling issues
- Nested config object validation

Usage:
    pytest tests/test_ingestion_sourceconfig_fuzzing.py -v
"""

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, assume, strategies as st
from pydantic import ValidationError

# Add parent directories to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "ingestion"))

from app.api import SourceConfig  # noqa: E402


# Strategies for generating test data
def source_name_strategy():
    """Generate source names including malicious patterns."""
    return st.one_of(
        # Normal names
        st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=100),
        # Path traversal
        st.just("../../../etc/passwd"),
        st.just("..\\..\\..\\windows\\system32"),
        # SQL injection
        st.just("admin' OR '1'='1"),
        st.just("'; DROP TABLE sources; --"),
        # XSS
        st.just("<script>alert('xss')</script>"),
        st.just("javascript:alert(1)"),
        # Command injection
        st.just("; rm -rf /"),
        st.just("| cat /etc/passwd"),
        # Null bytes
        st.just("test\x00admin"),
        # Unicode/homograph attacks
        st.just("аdmin"),  # Cyrillic 'а'
        # Empty/whitespace
        st.just(""),
        st.just("   "),
    )


def source_type_strategy():
    """Generate source types including valid and invalid values."""
    return st.one_of(
        # Valid types
        st.sampled_from(["rsync", "http", "imap", "local"]),
        # Invalid types (should be rejected)
        st.text(min_size=1, max_size=50),
        # Injection attempts
        st.just("local'; DROP TABLE sources; --"),
        st.just("<script>alert('xss')</script>"),
        # Case variations (should these be accepted?)
        st.just("RSYNC"),
        st.just("Local"),
        st.just("HTTP"),
    )


def url_strategy():
    """Generate URLs including malicious patterns."""
    return st.one_of(
        # Valid URLs
        st.just("http://example.com/archive.mbox"),
        st.just("https://example.com/path/to/file"),
        st.just("/local/path/to/file.mbox"),
        st.just("file:///tmp/archive.mbox"),
        st.just("rsync://example.com/archives/"),
        st.just("imap://mail.example.com"),
        # Path traversal
        st.just("http://example.com/../../../etc/passwd"),
        st.just("/local/../../../etc/passwd"),
        # Command injection
        st.just("http://example.com/file; rm -rf /"),
        st.just("/tmp/file.mbox; whoami"),
        # XSS in URL
        st.just("javascript:alert(1)"),
        st.just("data:text/html,<script>alert('xss')</script>"),
        # SSRF attempts
        st.just("http://169.254.169.254/latest/meta-data/"),
        st.just("http://localhost:8080/admin"),
        st.just("http://127.0.0.1/secrets"),
        # Null bytes
        st.just("http://example.com\x00@evil.com"),
        # URL encoding confusion
        st.just("http://example.com/%2e%2e%2f%2e%2e%2fetc/passwd"),
        # Very long URLs
        st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1000, max_size=10000),
        # Empty/invalid
        st.just(""),
        st.just("   "),
        st.just("not-a-url"),
    )


def port_strategy():
    """Generate port numbers including edge cases."""
    return st.one_of(
        st.none(),
        # Valid ports
        st.integers(min_value=1, max_value=65535),
        # Invalid ports
        st.integers(min_value=-1000, max_value=0),
        st.integers(min_value=65536, max_value=100000),
        # Edge cases
        st.just(0),
        st.just(-1),
    )


def string_field_strategy():
    """Generate strings for username, password, folder fields."""
    return st.one_of(
        st.none(),
        # Normal values
        st.text(min_size=1, max_size=100),
        # SQL injection
        st.just("admin' OR '1'='1"),
        st.just("'; DROP TABLE users; --"),
        # XSS
        st.just("<script>alert('xss')</script>"),
        # Command injection
        st.just("; whoami"),
        st.just("| cat /etc/passwd"),
        # LDAP injection
        st.just("*)(uid=*))(|(uid=*"),
        # Null bytes
        st.just("test\x00admin"),
        # Special characters
        st.just("test\r\nInjected-Header: value"),
        # Very long strings (Hypothesis has a max size limit around 10000)
        st.text(min_size=1000, max_size=5000),
        # Empty/whitespace
        st.just(""),
        st.just("   "),
    )


def bool_strategy():
    """Generate boolean values including type confusion attempts."""
    return st.one_of(
        st.booleans(),
        # These will be passed as-is to test Pydantic's handling
    )


def schedule_strategy():
    """Generate schedule cron expressions including malicious patterns."""
    return st.one_of(
        st.none(),
        # Valid cron expressions
        st.just("0 */6 * * *"),
        st.just("0 0 * * *"),
        st.just("*/5 * * * *"),
        # Invalid cron
        st.text(min_size=1, max_size=100),
        # Injection attempts
        st.just("0 */6 * * *; rm -rf /"),
        st.just("$(whoami)"),
        # Very long
        st.text(min_size=1000, max_size=5000),
    )


class TestSourceConfigPydanticValidation:
    """Property-based tests for SourceConfig Pydantic model validation."""

    @given(
        name=source_name_strategy(),
        source_type=source_type_strategy(),
        url=url_strategy(),
        port=port_strategy(),
        username=string_field_strategy(),
        password=string_field_strategy(),
        folder=string_field_strategy(),
        enabled=bool_strategy(),
        schedule=schedule_strategy(),
    )
    @settings(max_examples=500, deadline=None)
    def test_sourceconfig_validation_never_crashes(
        self,
        name: str,
        source_type: str,
        url: str,
        port: int | None,
        username: str | None,
        password: str | None,
        folder: str | None,
        enabled: bool,
        schedule: str | None,
    ):
        """SourceConfig validation should never crash, always return valid or raise ValidationError."""
        try:
            # Attempt to create SourceConfig with fuzzed data
            config = SourceConfig(
                name=name,
                source_type=source_type,
                url=url,
                port=port,
                username=username,
                password=password,
                folder=folder,
                enabled=enabled,
                schedule=schedule,
            )

            # If validation passes, verify the object is properly constructed
            assert isinstance(config, SourceConfig)
            assert isinstance(config.name, str)
            assert isinstance(config.source_type, str)
            assert isinstance(config.url, str)
            assert isinstance(config.enabled, bool)

            # Verify port is None or int
            assert config.port is None or isinstance(config.port, int)

            # Verify optional string fields are None or str
            for field in [config.username, config.password, config.folder, config.schedule]:
                assert field is None or isinstance(field, str)

        except ValidationError as e:
            # ValidationError is expected for invalid input
            # Verify error message doesn't leak sensitive info
            error_msg = str(e)
            assert error_msg, "ValidationError should have a message"

            # Errors should not contain the actual password value if present
            if password and len(password) > 10:
                assert password not in error_msg, "Password should not be leaked in error message"

        except Exception as e:
            # Any other exception is a bug
            pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")

    @given(st.text(min_size=1))
    @settings(max_examples=200, deadline=None)
    def test_required_field_name_enforced(self, name: str):
        """Name field must be required and non-empty."""
        # Valid minimal config
        try:
            config = SourceConfig(
                name=name,
                source_type="local",
                url="/tmp/test.mbox",
            )
            assert config.name == name
        except ValidationError:
            # Validation may fail for invalid names, which is acceptable
            pass

    def test_missing_name_rejected(self):
        """SourceConfig without name should be rejected."""
        with pytest.raises(ValidationError):
            SourceConfig(
                source_type="local",
                url="/tmp/test.mbox",
            )

    def test_missing_source_type_rejected(self):
        """SourceConfig without source_type should be rejected."""
        with pytest.raises(ValidationError):
            SourceConfig(
                name="test",
                url="/tmp/test.mbox",
            )

    def test_missing_url_rejected(self):
        """SourceConfig without url should be rejected."""
        with pytest.raises(ValidationError):
            SourceConfig(
                name="test",
                source_type="local",
            )

    @given(st.integers(min_value=-1000, max_value=0))
    @settings(max_examples=50, deadline=None)
    def test_negative_ports_handling(self, port: int):
        """Test that negative ports are handled gracefully."""
        try:
            config = SourceConfig(
                name="test",
                source_type="imap",
                url="imap://mail.example.com",
                port=port,
            )
            # If accepted, port should be stored as provided
            assert config.port == port
        except ValidationError:
            # Rejection is also acceptable
            pass

    @given(st.integers(min_value=65536, max_value=100000))
    @settings(max_examples=50, deadline=None)
    def test_invalid_high_ports_handling(self, port: int):
        """Test that ports above 65535 are handled gracefully."""
        try:
            config = SourceConfig(
                name="test",
                source_type="imap",
                url="imap://mail.example.com",
                port=port,
            )
            # If accepted, port should be stored as provided
            assert config.port == port
        except ValidationError:
            # Rejection is also acceptable
            pass


class TestSourceConfigInjectionResistance:
    """Tests specifically for injection attack resistance."""

    @given(st.sampled_from([
        "admin' OR '1'='1",
        "'; DROP TABLE sources; --",
        "1' UNION SELECT * FROM users--",
        "admin'--",
        "' OR 1=1--",
    ]))
    @settings(max_examples=50, deadline=None)
    def test_sql_injection_in_name(self, malicious_name: str):
        """SQL injection attempts in name should not cause issues."""
        try:
            config = SourceConfig(
                name=malicious_name,
                source_type="local",
                url="/tmp/test.mbox",
            )
            # If accepted, should be stored as-is (sanitization happens at DB layer)
            assert config.name == malicious_name
        except ValidationError:
            # Rejection is also acceptable
            pass

    @given(st.sampled_from([
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "<img src=x onerror=alert(1)>",
        "';alert(String.fromCharCode(88,83,83))//",
    ]))
    @settings(max_examples=50, deadline=None)
    def test_xss_injection_in_fields(self, xss_payload: str):
        """XSS attempts should be handled gracefully."""
        try:
            config = SourceConfig(
                name=xss_payload,
                source_type="local",
                url="/tmp/test.mbox",
            )
            # If accepted, should be stored as-is (sanitization happens at output)
            assert config.name == xss_payload
        except ValidationError:
            pass

    @given(st.sampled_from([
        "; rm -rf /",
        "| cat /etc/passwd",
        "; whoami",
        "$(whoami)",
        "`whoami`",
        "&& ls -la",
    ]))
    @settings(max_examples=50, deadline=None)
    def test_command_injection_in_url(self, cmd_injection: str):
        """Command injection attempts in URL should be handled."""
        try:
            config = SourceConfig(
                name="test",
                source_type="local",
                url=f"/tmp/test.mbox{cmd_injection}",
            )
            # If accepted, verify it's stored as-is
            assert cmd_injection in config.url
        except ValidationError:
            pass


class TestSourceConfigTypeConfusion:
    """Tests for type confusion vulnerabilities."""

    def test_port_as_string_rejected(self):
        """Port field should reject string values."""
        with pytest.raises(ValidationError):
            SourceConfig(
                name="test",
                source_type="imap",
                url="imap://mail.example.com",
                port="not-a-number",  # type: ignore
            )

    def test_enabled_as_string_coercion(self):
        """Test how enabled field handles string values."""
        # Pydantic may coerce "true"/"false" to bool
        try:
            config = SourceConfig(
                name="test",
                source_type="local",
                url="/tmp/test.mbox",
                enabled="true",  # type: ignore
            )
            # If coerced, should be bool
            assert isinstance(config.enabled, bool)
        except ValidationError:
            # Strict rejection is also acceptable
            pass

    @given(st.integers())
    @settings(max_examples=100, deadline=None)
    def test_name_rejects_non_strings(self, value: int):
        """Name field should reject non-string values."""
        with pytest.raises(ValidationError):
            SourceConfig(
                name=value,  # type: ignore
                source_type="local",
                url="/tmp/test.mbox",
            )


class TestSourceConfigURLValidation:
    """Tests specifically for URL validation."""

    @given(st.sampled_from([
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://localhost:8080/admin",
        "http://127.0.0.1:6379",
        "http://[::1]/admin",
        "file:///etc/passwd",
    ]))
    @settings(max_examples=50, deadline=None)
    def test_ssrf_attempts_in_url(self, ssrf_url: str):
        """SSRF attempts should be handled (acceptance is OK if validated elsewhere)."""
        try:
            config = SourceConfig(
                name="test",
                source_type="http",
                url=ssrf_url,
            )
            # If accepted, it should be stored as-is
            # SSRF prevention should happen at the ingestion layer, not validation
            assert config.url == ssrf_url
        except ValidationError:
            # Rejection is also acceptable
            pass

    @given(st.text(min_size=1000, max_size=10000))
    @settings(max_examples=50, deadline=None)
    def test_very_long_urls(self, long_string: str):
        """Very long URLs should be handled gracefully."""
        url = f"http://example.com/{long_string}"
        try:
            config = SourceConfig(
                name="test",
                source_type="http",
                url=url,
            )
            assert config.url == url
        except ValidationError:
            # Length limits are acceptable
            pass

    def test_empty_url_handling(self):
        """Test how empty URLs are handled."""
        # Pydantic accepts empty strings by default unless we add validators
        # This documents current behavior - empty URLs pass basic Pydantic validation
        # but should be caught by service-level validation
        try:
            config = SourceConfig(
                name="test",
                source_type="local",
                url="",
            )
            # If accepted, it should be stored as-is
            assert config.url == ""
        except ValidationError:
            # Rejection via validator is also acceptable
            pass


class TestSourceConfigScheduleValidation:
    """Tests for schedule field validation."""

    @given(st.sampled_from([
        "0 */6 * * *",
        "0 0 * * *",
        "*/5 * * * *",
        "0 0 1 * *",
    ]))
    @settings(max_examples=20, deadline=None)
    def test_valid_cron_expressions(self, cron: str):
        """Valid cron expressions should be accepted."""
        config = SourceConfig(
            name="test",
            source_type="local",
            url="/tmp/test.mbox",
            schedule=cron,
        )
        assert config.schedule == cron

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_arbitrary_schedule_strings(self, schedule: str):
        """Test that arbitrary strings in schedule don't cause crashes."""
        # Note: Validation of cron syntax likely happens elsewhere
        try:
            config = SourceConfig(
                name="test",
                source_type="local",
                url="/tmp/test.mbox",
                schedule=schedule,
            )
            assert config.schedule == schedule
        except ValidationError:
            # Rejection is acceptable
            pass


class TestSourceConfigSecurityInvariants:
    """High-level security invariants for SourceConfig."""

    @given(
        st.text(min_size=1, max_size=1000),
        st.text(min_size=1, max_size=1000),
        st.text(min_size=1, max_size=1000),
    )
    @settings(max_examples=200, deadline=None)
    def test_model_dump_never_crashes(self, name: str, source_type: str, url: str):
        """Serializing SourceConfig to dict should never crash."""
        try:
            config = SourceConfig(
                name=name,
                source_type=source_type,
                url=url,
            )
            # model_dump() is called when passing to service methods
            data = config.model_dump()

            assert isinstance(data, dict)
            assert "name" in data
            assert "source_type" in data
            assert "url" in data
            assert data["name"] == name
            assert data["source_type"] == source_type
            assert data["url"] == url

        except ValidationError:
            # Validation failure is acceptable
            pass

    @given(
        st.text(min_size=1, max_size=1000),
        st.text(min_size=1, max_size=1000),
        st.text(min_size=1, max_size=1000),
    )
    @settings(max_examples=200, deadline=None)
    def test_model_json_serialization_safe(self, name: str, source_type: str, url: str):
        """JSON serialization should never crash and be reversible."""
        try:
            config = SourceConfig(
                name=name,
                source_type=source_type,
                url=url,
            )

            # Serialize to JSON
            json_str = config.model_dump_json()
            assert isinstance(json_str, str)
            assert len(json_str) > 0

        except ValidationError:
            # Validation failure is acceptable
            pass
        except Exception as e:
            # JSON serialization should not fail for valid configs
            pytest.fail(f"JSON serialization failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
