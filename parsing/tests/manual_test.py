#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Manual end-to-end test for parsing service."""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copilot_events import NoopPublisher, NoopSubscriber
from copilot_storage import InMemoryDocumentStore

from app.service import ParsingService

def main():
    """Test parsing service with sample mbox."""
    
    # Setup
    print("Setting up parsing service...")
    document_store = InMemoryDocumentStore()
    document_store.connect()
    
    publisher = NoopPublisher()
    publisher.connect()
    
    subscriber = NoopSubscriber()
    subscriber.connect()
    
    service = ParsingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
    )
    
    # Test with sample mbox
    mbox_path = "/tmp/test_parsing_data/sample.mbox"
    
    if not os.path.exists(mbox_path):
        print(f"Error: Sample mbox not found at {mbox_path}")
        return 1
    
    print(f"Processing mbox: {mbox_path}")
    
    archive_data = {
        "archive_id": "test-manual-archive",
        "file_path": mbox_path,
    }
    
    service.process_archive(archive_data)
    
    # Check results
    print("\n=== Results ===")
    stats = service.get_stats()
    print(f"Archives processed: {stats['archives_processed']}")
    print(f"Messages parsed: {stats['messages_parsed']}")
    print(f"Threads created: {stats['threads_created']}")
    print(f"Processing time: {stats['last_processing_time_seconds']:.3f}s")
    
    # Show messages
    messages = document_store.query_documents("messages", {})
    print(f"\n=== Messages ({len(messages)}) ===")
    for msg in messages:
        print(f"  - {msg['message_id']}")
        print(f"    Subject: {msg['subject']}")
        print(f"    From: {msg['from']['name']} <{msg['from']['email']}>")
        print(f"    Drafts: {msg['draft_mentions']}")
        print(f"    Body preview: {msg['body_normalized'][:100]}...")
        print()
    
    # Show threads
    threads = document_store.query_documents("threads", {})
    print(f"\n=== Threads ({len(threads)}) ===")
    for thread in threads:
        print(f"  - {thread['thread_id']}")
        print(f"    Subject: {thread['subject']}")
        print(f"    Messages: {thread['message_count']}")
        print(f"    Participants: {len(thread['participants'])}")
        print(f"    Drafts: {thread['draft_mentions']}")
        print()
    
    print("\n✅ Test completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
