#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example integration with summarization or other services.

This script demonstrates how the draft diff provider abstraction layer
can be integrated into services like summarization, reporting, etc.
"""

import os
from draft_diff import create_diff_provider


class DraftSummaryService:
    """Example service that uses draft diff provider to summarize draft changes.
    
    This demonstrates how the summarization service (or any other service)
    could integrate the draft diff provider abstraction layer.
    """
    
    def __init__(self, diff_provider=None):
        """Initialize the service.
        
        Args:
            diff_provider: Optional draft diff provider. If None, creates from env.
        """
        # Create diff provider from environment if not provided
        self.diff_provider = diff_provider or create_diff_provider()
        
    def summarize_draft_changes(self, draft_name: str, old_version: str, new_version: str) -> dict:
        """Summarize changes between two draft versions.
        
        Args:
            draft_name: Name of the draft
            old_version: Old version identifier
            new_version: New version identifier
            
        Returns:
            Dictionary containing summary information
        """
        # Fetch the diff
        diff = self.diff_provider.getdiff(draft_name, old_version, new_version)
        
        # In a real implementation, you would:
        # 1. Parse the diff content
        # 2. Use an LLM to generate a summary
        # 3. Extract key changes
        # 4. Identify consensus points
        
        # For this example, we'll just create a simple summary
        return {
            "draft_name": diff.draft_name,
            "version_range": f"{diff.version_a} -> {diff.version_b}",
            "format": diff.format,
            "source": diff.source,
            "url": diff.url,
            "content_length": len(diff.content),
            "summary": self._generate_simple_summary(diff),
        }
    
    def _generate_simple_summary(self, diff) -> str:
        """Generate a simple summary from diff content.
        
        In a real implementation, this would use an LLM.
        
        Args:
            diff: DraftDiff object
            
        Returns:
            Summary string
        """
        lines = diff.content.split('\n')
        return (
            f"Changes between {diff.draft_name} versions "
            f"{diff.version_a} and {diff.version_b}:\n"
            f"- Total content length: {len(diff.content)} characters\n"
            f"- Total lines: {len(lines)}\n"
            f"- Source: {diff.source}"
        )


class DraftTrackingService:
    """Example service that tracks draft evolution using diff provider."""
    
    def __init__(self, diff_provider=None):
        """Initialize the service.
        
        Args:
            diff_provider: Optional draft diff provider. If None, creates from env.
        """
        self.diff_provider = diff_provider or create_diff_provider()
        self.tracked_diffs = []
    
    def track_draft_version(self, draft_name: str, old_version: str, new_version: str):
        """Track a new version of a draft.
        
        Args:
            draft_name: Name of the draft
            old_version: Previous version
            new_version: New version
        """
        diff = self.diff_provider.getdiff(draft_name, old_version, new_version)
        
        self.tracked_diffs.append({
            "draft": diff.draft_name,
            "versions": f"{diff.version_a}->{diff.version_b}",
            "timestamp": "2025-01-01T00:00:00Z",  # In real impl, use actual timestamp
            "source": diff.source,
            "url": diff.url,
        })
    
    def get_draft_history(self, draft_name: str) -> list:
        """Get tracked history for a draft.
        
        Args:
            draft_name: Name of the draft
            
        Returns:
            List of tracked diff records
        """
        return [d for d in self.tracked_diffs if d["draft"] == draft_name]


def example_summarization_integration():
    """Demonstrate integration with summarization service."""
    print("=" * 60)
    print("Example: Summarization Service Integration")
    print("=" * 60)
    
    # Create service with mock provider for testing
    service = DraftSummaryService(create_diff_provider("mock"))
    
    # Summarize draft changes
    summary = service.summarize_draft_changes(
        draft_name="draft-ietf-quic-transport",
        old_version="01",
        new_version="02"
    )
    
    print("\nSummary Result:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print()


def example_tracking_integration():
    """Demonstrate integration with draft tracking service."""
    print("=" * 60)
    print("Example: Draft Tracking Service Integration")
    print("=" * 60)
    
    # Create service with mock provider
    service = DraftTrackingService(create_diff_provider("mock"))
    
    # Track several draft versions
    drafts_to_track = [
        ("draft-ietf-quic-transport", "01", "02"),
        ("draft-ietf-quic-transport", "02", "03"),
        ("draft-ietf-http3", "00", "01"),
    ]
    
    for draft, old_ver, new_ver in drafts_to_track:
        service.track_draft_version(draft, old_ver, new_ver)
        print(f"Tracked: {draft} {old_ver} -> {new_ver}")
    
    # Get history for a specific draft
    print("\nHistory for draft-ietf-quic-transport:")
    history = service.get_draft_history("draft-ietf-quic-transport")
    for record in history:
        print(f"  {record['versions']} - {record['url']}")
    print()


def example_environment_based_config():
    """Demonstrate environment-based configuration."""
    print("=" * 60)
    print("Example: Environment-Based Configuration")
    print("=" * 60)
    
    # Set environment variables
    os.environ["DRAFT_DIFF_PROVIDER"] = "mock"
    os.environ["DRAFT_DIFF_FORMAT"] = "markdown"
    
    # Create service - it will automatically use environment config
    service = DraftSummaryService()  # No provider argument
    
    summary = service.summarize_draft_changes(
        "draft-example",
        "10",
        "11"
    )
    
    print(f"\nUsing provider: {summary['source']}")
    print(f"Format: {summary['format']}")
    
    # Clean up
    os.environ.pop("DRAFT_DIFF_PROVIDER", None)
    os.environ.pop("DRAFT_DIFF_FORMAT", None)
    print()


def main():
    """Run all integration examples."""
    print("\nDraft Diff Provider Integration Examples")
    print("=" * 60)
    print()
    
    example_summarization_integration()
    example_tracking_integration()
    example_environment_based_config()
    
    print("=" * 60)
    print("Integration examples completed!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("- Services can use create_diff_provider() for automatic config")
    print("- Environment variables control provider selection")
    print("- Mock provider enables testing without external dependencies")
    print("- Abstract interface makes it easy to swap providers")


if __name__ == "__main__":
    main()
