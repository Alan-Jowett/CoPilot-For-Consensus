#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the copilot_draft_diff module.

This script demonstrates how to use the draft diff provider abstraction layer
to fetch and display draft diffs from different sources.
"""

from copilot_draft_diff import create_diff_provider, MockDiffProvider, DraftDiff


def example_basic_usage():
    """Demonstrate basic usage with mock provider."""
    print("=" * 60)
    print("Example 1: Basic usage with mock provider")
    print("=" * 60)

    # Create a mock provider
    provider = create_diff_provider("mock")

    # Fetch a diff
    diff = provider.getdiff("draft-ietf-quic-transport", "01", "02")

    print(f"Draft: {diff.draft_name}")
    print(f"Versions: {diff.version_a} -> {diff.version_b}")
    print(f"Format: {diff.format}")
    print(f"Source: {diff.source}")
    print(f"URL: {diff.url}")
    print(f"\nContent:\n{diff.content}")
    print()


def example_different_formats():
    """Demonstrate different output formats."""
    print("=" * 60)
    print("Example 2: Different output formats")
    print("=" * 60)

    formats = ["text", "html", "markdown"]

    for fmt in formats:
        print(f"\n--- Format: {fmt} ---")
        provider = create_diff_provider("mock", {"default_format": fmt})
        diff = provider.getdiff("draft-example", "00", "01")
        print(diff.content[:200] + "..." if len(diff.content) > 200 else diff.content)
        print()


def example_predefined_mock():
    """Demonstrate using predefined mock diffs."""
    print("=" * 60)
    print("Example 3: Predefined mock diffs")
    print("=" * 60)

    # Create a custom predefined diff
    custom_diff = DraftDiff(
        draft_name="draft-custom",
        version_a="03",
        version_b="04",
        format="text",
        content="""Custom Diff for draft-custom
Version 03 -> 04

Changes:
- Added new section on security considerations
- Fixed typos in section 3.2
- Updated references to RFC 9000
""",
        source="mock",
        url="custom://draft-custom/03..04",
        metadata={"lines_added": 42, "lines_removed": 10}
    )

    # Create provider with predefined diff
    provider = MockDiffProvider(
        mock_diffs={
            ("draft-custom", "03", "04"): custom_diff
        }
    )

    # Fetch the predefined diff
    diff = provider.getdiff("draft-custom", "03", "04")

    print(f"Draft: {diff.draft_name}")
    print(f"Versions: {diff.version_a} -> {diff.version_b}")
    print(f"Metadata: {diff.metadata}")
    print(f"\nContent:\n{diff.content}")
    print()


def example_to_dict():
    """Demonstrate converting diff to dictionary."""
    print("=" * 60)
    print("Example 4: Converting to dictionary")
    print("=" * 60)

    provider = create_diff_provider("mock")
    diff = provider.getdiff("draft-test", "05", "06")

    # Convert to dictionary (useful for JSON serialization)
    diff_dict = diff.to_dict()

    print("Dictionary representation:")
    for key, value in diff_dict.items():
        if key == "content":
            print(f"  {key}: {value[:50]}..." if value and len(value) > 50 else f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    print()


def main():
    """Run all examples."""
    print("\nDraft Diff Provider Examples")
    print("=" * 60)
    print()

    example_basic_usage()
    example_different_formats()
    example_predefined_mock()
    example_to_dict()

    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
