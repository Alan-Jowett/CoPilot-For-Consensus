# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example hypothesis property-based testing.

Hypothesis generates test cases based on properties and invariants you specify.
It's excellent for testing that functions behave correctly across a wide range
of inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings


@given(st.text())
@settings(max_examples=100)
def test_string_reversal_is_involutive(s: str) -> None:
    """Test that reversing a string twice returns the original.
    
    This is a simple example of a property test. Hypothesis will generate
    many different strings to verify this property holds.
    """
    assert s[::-1][::-1] == s


@given(st.lists(st.integers()))
@settings(max_examples=100)
def test_list_length_preserved_after_sort(lst: list[int]) -> None:
    """Test that sorting doesn't change the length of a list.
    
    This tests an invariant: sorting should preserve the number of elements.
    """
    original_length = len(lst)
    sorted_list = sorted(lst)
    assert len(sorted_list) == original_length


@given(st.dictionaries(st.text(), st.integers()))
@settings(max_examples=100)
def test_dict_keys_preserved(d: dict[str, int]) -> None:
    """Test that dictionary operations preserve keys.
    
    This demonstrates testing data structure invariants.
    """
    keys_before = set(d.keys())
    
    # Create a copy and modify values
    d_copy = {k: v * 2 for k, v in d.items()}
    
    keys_after = set(d_copy.keys())
    assert keys_before == keys_after


@given(st.text(min_size=1), st.text())
@settings(max_examples=100)
def test_string_concatenation_contains_parts(prefix: str, suffix: str) -> None:
    """Test that concatenated strings contain their parts.
    
    This tests a basic property of string concatenation.
    """
    result = prefix + suffix
    assert prefix in result or len(prefix) == 0
    assert suffix in result or len(suffix) == 0


# Example of testing idempotency (important for message processing)
@given(st.text())
@settings(max_examples=50)
def test_idempotent_normalization(text: str) -> None:
    """Test that text normalization is idempotent.
    
    Applying normalization multiple times should give the same result.
    This is crucial for message processing where deduplication matters.
    """
    def normalize(s: str) -> str:
        """Simple normalization function."""
        return s.strip().lower()
    
    normalized_once = normalize(text)
    normalized_twice = normalize(normalized_once)
    
    assert normalized_once == normalized_twice, \
        "Normalization should be idempotent"


# Example of testing for expected exceptions
@given(st.integers())
@settings(max_examples=100)
def test_division_by_zero_handled(n: int) -> None:
    """Test that division by zero is handled gracefully.
    
    This shows how to test error handling with hypothesis.
    """
    def safe_divide(numerator: int, denominator: int) -> float | None:
        """Divide two numbers, returning None if denominator is zero."""
        if denominator == 0:
            return None
        return numerator / denominator
    
    result = safe_divide(n, 0)
    assert result is None, "Division by zero should return None"
    
    if n != 0:
        result = safe_divide(n, n)
        assert result == 1.0, "n/n should equal 1"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
