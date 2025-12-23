# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Demonstration test file showing how static analysis tools catch common errors.

This file contains examples of errors that would be caught by:
- Pylint (E0602, E1101)
- MyPy (type errors)
- Pyright (attribute access errors)

These examples help validate that the CI checks are working correctly.
"""


class SampleConfig:
    """Example configuration class."""

    def __init__(self) -> None:
        """Initialize with a known attribute."""
        self.host: str = "localhost"
        self.port: int = 8080


def test_valid_attribute_access() -> None:
    """Test that valid attribute access works correctly."""
    config = SampleConfig()
    assert config.host == "localhost"
    assert config.port == 8080


def test_valid_variable_usage() -> None:
    """Test that properly defined variables work correctly."""
    data = {"key": "value"}
    result = data.get("key")
    assert result == "value"


def test_optional_with_check() -> None:
    """Test that optional values are handled correctly with None checks."""
    value: str | None = "test"

    if value is not None:
        assert len(value) > 0


def test_type_safe_function() -> None:
    """Test that type-safe functions work correctly."""
    def process_data(input_str: str) -> int:
        """Process a string and return its length."""
        return len(input_str)

    result = process_data("hello")
    assert result == 5


# NOTE: The following commented examples would trigger static analysis errors:

# Example 1: E0602 - Undefined variable
# def test_undefined_variable():
#     result = undefined_variable_name  # E0602: Undefined variable
#     return result

# Example 2: E1101 - No member
# def test_nonexistent_attribute():
#     config = SampleConfig()
#     return config.hostname  # E1101: SampleConfig has no 'hostname' member

# Example 3: Type error (MyPy/Pyright)
# def test_type_mismatch():
#     def get_number() -> int:
#         return "not a number"  # Type error: returning str instead of int
#     return get_number()

# Example 4: Optional without None check (Pyright)
# def test_optional_without_check():
#     value: Optional[str] = None
#     return len(value)  # Error: value may be None
