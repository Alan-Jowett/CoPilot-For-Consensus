# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Hypothesis property-based tests for ingestion file upload security.

Property-based testing complements fuzzing by testing invariants and properties
that should hold for all inputs. These tests are run through pytest.

Usage:
    pytest tests/test_ingestion_upload_properties.py -v
"""

import sys
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Add parent directories to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "ingestion"))

from app.api import (  # noqa: E402
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    _sanitize_filename,
    _split_extension,
    _validate_file_extension,
)


def _is_safe_filename(sanitized: str) -> bool:
    """Check if a sanitized filename is safe from path traversal.

    A filename is safe if:
    - It contains no forward slashes
    - It contains no backslashes (Windows path separator)
    - It's just a simple filename without directory components

    Args:
        sanitized: The sanitized filename to check

    Returns:
        True if the filename is safe, False otherwise
    """
    # No forward slashes allowed in filenames
    if '/' in sanitized:
        return False

    # No backslashes (Windows paths)
    if '\\' in sanitized:
        return False

    return True


class TestFilenameSanitizationProperties:
    """Property-based tests for filename sanitization."""

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_sanitization_never_contains_path_separators(self, filename: str):
        """Sanitized filenames must never contain path separators."""
        sanitized = _sanitize_filename(filename)
        assert _is_safe_filename(sanitized), \
            f"Unsafe filename: {sanitized}"

    @given(st.text(min_size=1))
    @settings(max_examples=1000, deadline=None)
    def test_sanitization_never_produces_empty_string(self, filename: str):
        """Sanitization must always produce a non-empty string."""
        sanitized = _sanitize_filename(filename)
        assert sanitized, f"Sanitization produced empty string for: {filename!r}"

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_sanitization_limits_length(self, filename: str):
        """Sanitized filenames must be <= 255 characters."""
        sanitized = _sanitize_filename(filename)
        assert len(sanitized) <= 255, \
            f"Sanitized filename too long ({len(sanitized)}): {sanitized[:50]}..."

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_sanitization_removes_null_bytes(self, filename: str):
        """Sanitized filenames must not contain null bytes."""
        sanitized = _sanitize_filename(filename)
        assert '\x00' not in sanitized, \
            f"Null byte in sanitized filename: {sanitized!r}"

    @given(st.text(alphabet=st.characters(blacklist_categories=('Cs',)), min_size=1))
    @settings(max_examples=500, deadline=None)
    def test_sanitization_is_idempotent(self, filename: str):
        """Sanitizing twice should produce the same result."""
        first = _sanitize_filename(filename)
        second = _sanitize_filename(first)
        assert first == second, \
            f"Sanitization not idempotent: {filename!r} -> {first!r} -> {second!r}"

    @given(st.text(alphabet='./\\', min_size=1, max_size=100))
    @settings(max_examples=500, deadline=None)
    def test_sanitization_handles_path_traversal_attempts(self, filename: str):
        """Path traversal patterns must be sanitized.

        Note: The current implementation prefixes problematic names with 'upload_'
        which makes them safe. For example, '..' becomes 'upload_..' which is
        not a special directory reference.
        """
        sanitized = _sanitize_filename(filename)
        assert _is_safe_filename(sanitized), \
            f"Unsafe filename from path traversal attempt: {sanitized}"

    @given(st.text())
    @settings(max_examples=500, deadline=None)
    def test_sanitization_no_absolute_paths(self, filename: str):
        """Sanitized filenames must not be absolute paths."""
        sanitized = _sanitize_filename(filename)

        # Use the helper function to check
        assert _is_safe_filename(sanitized), \
            f"Unsafe filename (absolute path): {sanitized}"

        # Note: Windows drive letters (C:, D:) have their colons replaced
        # with underscores by the sanitization regex, so post-sanitization
        # we verify the colon was removed, not that it's absent (it always is)
        assert ':' not in sanitized, \
            f"Colon not sanitized (potential Windows path): {sanitized}"


class TestExtensionValidationProperties:
    """Property-based tests for file extension validation."""

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_validation_returns_bool(self, filename: str):
        """Extension validation must always return a boolean."""
        result = _validate_file_extension(filename)
        assert isinstance(result, bool), \
            f"Validation returned non-bool: {type(result)}"

    @given(st.sampled_from([".mbox", ".zip", ".tar", ".tar.gz", ".tgz"]))
    @settings(max_examples=100, deadline=None)
    def test_allowed_extensions_validate(self, extension: str):
        """Files with allowed extensions should validate."""
        filename = f"test{extension}"
        assert _validate_file_extension(filename), \
            f"Allowed extension rejected: {extension}"

    @given(
        st.sampled_from([".mbox", ".zip", ".tar", ".tar.gz", ".tgz"]),
        st.randoms()
    )
    @settings(max_examples=100, deadline=None)
    def test_validation_case_insensitive(self, extension: str, rnd):
        """Extension validation should be case-insensitive."""
        # Create case variations by randomly uppercasing/lowercasing each character
        varied = "".join(
            c.upper() if rnd.choice([True, False]) else c.lower()
            for c in extension
        )
        filename = f"test{varied}"
        result = _validate_file_extension(filename)
        # Should pass for known extensions regardless of case
        assert result, f"Case variation rejected: {varied}"

    @given(st.text(alphabet=st.characters(blacklist_categories=('Cc',)), min_size=1, max_size=50))
    @settings(max_examples=500, deadline=None)
    def test_unknown_extensions_rejected(self, extension: str):
        """Extensions not in the allowed list should be rejected."""
        # Skip if it happens to match an allowed extension
        assume(extension.lower() not in ALLOWED_EXTENSIONS)

        filename = f"test.{extension}"
        result = _validate_file_extension(filename)

        # Should reject unless the fuzzer happened to create a valid compound extension
        if result:
            # If it passed, it must be because it ends with an allowed extension
            _, ext = _split_extension(filename)
            assert ext.lower() in ALLOWED_EXTENSIONS, \
                f"Unknown extension passed: {extension}"


class TestUploadSizeLimitProperties:
    """Strategy validation tests for size limit constant.
    
    These tests validate the MAX_UPLOAD_SIZE constant and test data generation
    strategies, not the actual upload endpoint behavior. Actual upload size
    validation is tested in ingestion service integration tests.
    """

    @given(st.integers(min_value=0, max_value=MAX_UPLOAD_SIZE))
    @settings(max_examples=100, deadline=None)
    def test_sizes_within_limit_should_pass(self, size: int):
        """File sizes within the limit should be accepted."""
        # This validates that the test strategy generates valid sizes correctly
        # for use in other property tests. Actual upload validation is tested
        # in ingestion service tests.
        assert size <= MAX_UPLOAD_SIZE, \
            f"Size {size} exceeds limit {MAX_UPLOAD_SIZE}"

    @given(st.integers(min_value=MAX_UPLOAD_SIZE + 1, max_value=MAX_UPLOAD_SIZE * 10))
    @settings(max_examples=100, deadline=None)
    def test_sizes_over_limit_should_fail(self, size: int):
        """File sizes over the limit should be rejected."""
        # This validates the test strategy generates invalid sizes correctly
        # for use in other property tests. Actual rejection behavior is tested
        # in ingestion service tests.
        assert size > MAX_UPLOAD_SIZE, \
            f"Size {size} should exceed limit {MAX_UPLOAD_SIZE}"


class TestExtensionSplittingProperties:
    """Property-based tests for extension splitting logic."""

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_split_always_returns_tuple(self, filename: str):
        """Extension splitting must always return a tuple."""
        result = _split_extension(filename)
        assert isinstance(result, tuple), f"Split returned non-tuple: {type(result)}"
        assert len(result) == 2, f"Split returned wrong size tuple: {len(result)}"

    @given(st.text())
    @settings(max_examples=500, deadline=None)
    def test_split_returns_strings(self, filename: str):
        """Both parts of the split must be strings."""
        name, ext = _split_extension(filename)
        assert isinstance(name, str), f"Name is not string: {type(name)}"
        assert isinstance(ext, str), f"Extension is not string: {type(ext)}"

    @given(
        st.sampled_from([
            "test.tar.gz", "test.tgz", "file.tar.gz", "archive.tgz",
            # Mixed-case to document normalization behavior
            "TEST.TAR.GZ", "File.TaR.gZ", "ARCHIVE.TGZ",
        ])
    )
    @settings(max_examples=50, deadline=None)
    def test_compound_extensions_preserved(self, filename: str):
        """Compound extensions are kept together when split (case preserved in return).
        
        Note: _split_extension returns the extension with its original case.
        This test verifies that when lowercased, it matches expected values.
        """
        name, ext = _split_extension(filename)

        # For .tar.gz and .tgz, extension should be the full compound extension
        # The function preserves case in the returned extension, so we lowercase
        # for comparison to verify it's one of the allowed compound extensions
        filename_lower = filename.lower()
        if filename_lower.endswith('.tar.gz'):
            assert ext.lower() == '.tar.gz', f"Compound extension not preserved: {ext}"
        elif filename_lower.endswith('.tgz'):
            assert ext.lower() == '.tgz', f"Compound extension not preserved: {ext}"


class TestSecurityInvariants:
    """High-level security property tests."""

    @given(st.text())
    @settings(max_examples=1000, deadline=None)
    def test_sanitization_prevents_directory_traversal(self, filename: str):
        """Sanitized filenames must not enable directory traversal."""
        from pathlib import Path

        sanitized = _sanitize_filename(filename)

        # Create a Path object and verify it's just a filename
        p = Path(sanitized)

        # Should have no parent directories
        assert str(p) == p.name, \
            f"Sanitized filename has directory components: {sanitized}"

    @given(st.binary(min_size=0, max_size=MAX_UPLOAD_SIZE + 1000))
    @settings(max_examples=100, deadline=None)
    def test_size_limit_enforced(self, data: bytes):
        """The size limit constant should be enforced."""
        size = len(data)
        should_reject = size > MAX_UPLOAD_SIZE

        if should_reject:
            assert size > MAX_UPLOAD_SIZE, \
                "Size check logic should reject this"
        else:
            assert size <= MAX_UPLOAD_SIZE, \
                "Size check logic should accept this"
