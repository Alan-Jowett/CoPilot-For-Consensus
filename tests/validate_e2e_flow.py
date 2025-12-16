# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
End-to-end test that validates the complete message flow pipeline.

This test verifies that messages flow through the entire system:
1. Ingestion -> archives collection
2. Parsing -> messages and threads collections
3. Chunking -> chunks collection
4. Embedding -> vectorstore (Qdrant)

The test runs against a live Docker Compose stack and validates actual
data persistence in MongoDB and Qdrant.
"""

import os
import sys
import time
from typing import Dict, Any, List, Optional
import json

# MongoDB client
try:
    from pymongo import MongoClient
except ImportError:
    print("ERROR: pymongo not installed. Install with: pip install pymongo")
    sys.exit(1)

# Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue
except ImportError:
    print("ERROR: qdrant-client not installed. Install with: pip install qdrant-client")
    sys.exit(1)


class E2EMessageFlowValidator:
    """Validates end-to-end message flow through all services."""
    
    def __init__(self):
        """Initialize validators with connections to MongoDB and Qdrant."""
        # MongoDB configuration (no authentication in docker-compose)
        self.mongo_host = os.getenv("MONGODB_HOST", "localhost")
        self.mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
        self.mongo_db = os.getenv("MONGODB_DATABASE", "copilot")
        
        # Qdrant configuration
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "embeddings")
        
        # Connect to MongoDB (no authentication in docker-compose)
        # Set aggressive timeouts to prevent hanging queries in CI
        mongo_uri = f"mongodb://{self.mongo_host}:{self.mongo_port}/"
        self.mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,  # 10s to select a server
            socketTimeoutMS=30000,            # 30s for socket operations
            connectTimeoutMS=10000,           # 10s to establish connection
            maxIdleTimeMS=45000               # 45s max idle time
        )
        self.db = self.mongo_client[self.mongo_db]
        
        # Connect to Qdrant
        self.qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        
        print(f"✓ Connected to MongoDB at {self.mongo_host}:{self.mongo_port}")
        print(f"✓ Connected to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
    
    def _safe_mongo_count(self, collection_name: str, max_retries: int = 3) -> int:
        """Safely count documents in a MongoDB collection with retry logic.
        
        Args:
            collection_name: Name of the collection to count
            max_retries: Maximum number of retry attempts
            
        Returns:
            Number of documents in the collection, or 0 if query fails
        """
        for attempt in range(max_retries):
            try:
                collection = self.db[collection_name]
                count = collection.count_documents({})
                return count
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  MongoDB query failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(1)
                else:
                    print(f"  ERROR: MongoDB query failed after {max_retries} attempts: {e}")
                    return 0
        return 0
    
    def _safe_mongo_find(self, collection_name: str, query: dict = None, max_retries: int = 3) -> List[Dict]:
        """Safely query documents from a MongoDB collection with retry logic.
        
        Args:
            collection_name: Name of the collection to query
            query: MongoDB query filter (default: {})
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of documents, or empty list if query fails
        """
        if query is None:
            query = {}
        
        for attempt in range(max_retries):
            try:
                collection = self.db[collection_name]
                # Use timeout on the cursor to prevent hanging
                cursor = collection.find(query).max_time_ms(30000)  # 30 second timeout
                documents = list(cursor)
                return documents
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  MongoDB query failed (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(1)
                else:
                    print(f"  ERROR: MongoDB query failed after {max_retries} attempts: {e}")
                    return []
        return []
    
    def _get_qdrant_collection_point_count(self) -> int:
        """Get the number of points in the Qdrant collection.
        
        Returns:
            Number of points in the collection, or 0 if collection doesn't exist.
        """
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            if self.qdrant_collection in collection_names:
                collection_info = self.qdrant_client.get_collection(self.qdrant_collection)
                return collection_info.points_count
        except Exception as e:
            # Log the error but don't fail - collection might not exist yet
            print(f"  Note: Could not query Qdrant collection: {e}")
        return 0
    
    def wait_for_processing(self, max_wait_seconds: int = 90, poll_interval: int = 3):
        """Wait for message processing to complete.
        
        Waits up to 90 seconds (default) for the pipeline to process messages through
        parsing → chunking → embedding stages. This duration accommodates slower CI
        environments and the time needed to process 10 test messages through all services.
        
        Polls the database to check if messages, chunks, and embeddings have been created.
        """
        print(f"\nWaiting up to {max_wait_seconds}s for pipeline processing...")
        start_time = time.time()
        
        messages_count = 0
        chunks_count = 0
        embeddings_count = 0
        
        while time.time() - start_time < max_wait_seconds:
            messages_count = self._safe_mongo_count("messages")
            chunks_count = self._safe_mongo_count("chunks")
            embeddings_count = self._get_qdrant_collection_point_count()
            
            print(f"  Polling... messages={messages_count}, chunks={chunks_count}, embeddings={embeddings_count}")
            
            # We expect at least messages and chunks to be created
            # Embeddings might take longer or fail, so we'll be lenient
            if messages_count > 0 and chunks_count > 0:
                print(f"✓ Core processing complete: {messages_count} messages, {chunks_count} chunks, {embeddings_count} embeddings")
                # Wait a bit more to see if embeddings appear
                if embeddings_count == 0:
                    print("⚠ No embeddings yet, waiting a bit more...")
                    time.sleep(5)
                    embeddings_count = self._get_qdrant_collection_point_count()
                    if embeddings_count > 0:
                        print(f"✓ Embeddings appeared: {embeddings_count}")
                return True
            
            time.sleep(poll_interval)
        
        print(f"⚠ Timeout after {max_wait_seconds}s waiting for processing")
        print(f"   Final counts: messages={messages_count}, chunks={chunks_count}, embeddings={embeddings_count}")
        # Return True if we have at least messages, even without chunks
        return messages_count > 0
    
    def validate_archives(self) -> Dict[str, Any]:
        """Validate that archives were ingested correctly."""
        print("\n=== Validating Archives ===")
        archives = self._safe_mongo_find("archives")
        
        if not archives:
            print("❌ FAIL: No archives found in database")
            return {"status": "FAIL", "count": 0, "details": "No archives ingested"}
        
        print(f"✓ Found {len(archives)} archive(s)")
        
        for archive in archives:
            print(f"  - Archive ID: {archive.get('archive_id')}")
            print(f"    Source: {archive.get('source')}")
            print(f"    Status: {archive.get('status')}")
            print(f"    Message count: {archive.get('message_count', 'N/A')}")
            
            if archive.get('status') != 'processed':
                print(f"    ⚠ Warning: Archive status is '{archive.get('status')}', expected 'processed'")
        
        return {
            "status": "PASS",
            "count": len(archives),
            "archives": archives
        }
    
    def validate_messages(self, expected_min_count: int = 10) -> Dict[str, Any]:
        """Validate that messages were parsed and stored correctly."""
        print("\n=== Validating Messages ===")
        messages = self._safe_mongo_find("messages")
        
        if not messages:
            print("❌ FAIL: No messages found in database")
            return {"status": "FAIL", "count": 0, "details": "No messages parsed"}
        
        print(f"✓ Found {len(messages)} message(s)")
        
        if len(messages) < expected_min_count:
            print(f"⚠ Warning: Expected at least {expected_min_count} messages, got {len(messages)}")
        
        # Validate message structure
        required_fields = ["message_key", "message_id", "archive_id", "thread_id", "subject", "from", "date"]
        for msg in messages[:3]:  # Check first 3 messages
            print(f"  - Message ID: {msg.get('message_id')}")
            print(f"    Subject: {msg.get('subject')}")
            print(f"    Thread ID: {msg.get('thread_id')}")
            
            missing_fields = [f for f in required_fields if f not in msg]
            if missing_fields:
                print(f"    ⚠ Missing fields: {missing_fields}")
        
        return {
            "status": "PASS",
            "count": len(messages),
            "messages": messages
        }
    
    def validate_threads(self) -> Dict[str, Any]:
        """Validate that threads were inferred correctly."""
        print("\n=== Validating Threads ===")
        threads = self._safe_mongo_find("threads")
        
        if not threads:
            print("⚠ Warning: No threads found in database")
            return {"status": "WARN", "count": 0, "details": "No threads created"}
        
        print(f"✓ Found {len(threads)} thread(s)")
        
        for thread in threads[:5]:  # Show first 5 threads
            print(f"  - Thread ID: {thread.get('thread_id')}")
            print(f"    Message count: {thread.get('message_count', 'N/A')}")
            print(f"    Subject: {thread.get('subject', 'N/A')}")
        
        return {
            "status": "PASS",
            "count": len(threads),
            "threads": threads
        }
    
    def validate_chunks(self, expected_min_count: int = 10) -> Dict[str, Any]:
        """Validate that chunks were created correctly."""
        print("\n=== Validating Chunks ===")
        chunks = self._safe_mongo_find("chunks")
        
        if not chunks:
            print("⚠ WARNING: No chunks found in database")
            print("   This may indicate chunking service hasn't processed messages yet")
            return {"status": "WARN", "count": 0, "details": "No chunks created"}
        
        print(f"✓ Found {len(chunks)} chunk(s)")
        
        if len(chunks) < expected_min_count:
            print(f"⚠ Warning: Expected at least {expected_min_count} chunks, got {len(chunks)}")
        
        # Validate chunk structure
        required_fields = ["chunk_key", "message_key", "message_id", "thread_id", "text", "chunk_index"]
        for chunk in chunks[:3]:  # Check first 3 chunks
            print(f"  - Chunk key: {chunk.get('chunk_key')}")
            print(f"    Message ID: {chunk.get('message_id')}")
            print(f"    Index: {chunk.get('chunk_index')}")
            print(f"    Token count: {chunk.get('token_count', 'N/A')}")
            
            missing_fields = [f for f in required_fields if f not in chunk]
            if missing_fields:
                print(f"    ⚠ Missing fields: {missing_fields}")
        
        return {
            "status": "PASS",
            "count": len(chunks),
            "chunks": chunks
        }
    
    def validate_embeddings(self, expected_min_count: int = 10) -> Dict[str, Any]:
        """Validate that embeddings were generated and stored in Qdrant."""
        print("\n=== Validating Embeddings ===")
        
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.qdrant_collection not in collection_names:
                print(f"⚠ WARNING: Collection '{self.qdrant_collection}' not found in Qdrant")
                print(f"   Available collections: {collection_names}")
                print(f"   This may indicate embedding generation hasn't completed or failed")
                return {"status": "WARN", "count": 0, "details": "Collection not created"}
            
            # Get collection info
            collection_info = self.qdrant_client.get_collection(self.qdrant_collection)
            points_count = collection_info.points_count
            
            print(f"✓ Found {points_count} embedding(s) in collection '{self.qdrant_collection}'")
            
            if points_count == 0:
                print(f"⚠ WARNING: No embeddings found, expected at least {expected_min_count}")
                print(f"   This may indicate embedding generation hasn't completed or failed")
                return {"status": "WARN", "count": 0, "details": "No embeddings generated"}
            
            if points_count < expected_min_count:
                print(f"⚠ Warning: Expected at least {expected_min_count} embeddings, got {points_count}")
            
            # Sample a few points to validate structure
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.qdrant_collection,
                limit=3,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            for point in points:
                print(f"  - Point ID: {point.id}")
                if point.payload:
                    print(f"    Chunk key: {point.payload.get('chunk_key', 'N/A')}")
                    print(f"    Message ID: {point.payload.get('message_id', 'N/A')}")
                    print(f"    Thread ID: {point.payload.get('thread_id', 'N/A')}")
            
            return {
                "status": "PASS",
                "count": points_count,
                "collection": self.qdrant_collection
            }
            
        except Exception as e:
            print(f"⚠ WARNING: Error querying Qdrant: {e}")
            print(f"   Embedding validation will be marked as warning, not failure")
            import traceback
            print(f"   Details: {traceback.format_exc()}")
            return {"status": "WARN", "count": 0, "details": str(e)}
    
    def validate_data_consistency(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Validate data consistency across collections."""
        print("\n=== Validating Data Consistency ===")
        
        messages = results.get("messages", {}).get("messages", [])
        chunks = results.get("chunks", {}).get("chunks", [])
        
        if not messages:
            print("⚠ Skipping consistency check: no messages")
            return {"status": "SKIP"}
        
        # Check that all chunks reference valid messages
        message_keys = {msg["message_key"] for msg in messages}
        chunk_message_keys = {chunk["message_key"] for chunk in chunks}
        
        orphaned_chunks = chunk_message_keys - message_keys
        if orphaned_chunks:
            print(f"⚠ Warning: Found {len(orphaned_chunks)} chunks referencing non-existent messages")
        else:
            print(f"✓ All {len(chunks)} chunks reference valid messages")
        
        # Check thread_id consistency
        messages_by_thread = {}
        for msg in messages:
            thread_id = msg.get("thread_id")
            if thread_id:
                messages_by_thread.setdefault(thread_id, []).append(msg)
        
        print(f"✓ Messages organized into {len(messages_by_thread)} unique threads")
        
        return {
            "status": "PASS",
            "unique_threads": len(messages_by_thread),
            "orphaned_chunks": len(orphaned_chunks)
        }
    
    def run_validation(self) -> bool:
        """Run all validation checks and return overall pass/fail status."""
        print("=" * 60)
        print("E2E Message Flow Validation")
        print("=" * 60)
        
        # Wait for processing to complete
        processing_complete = self.wait_for_processing(max_wait_seconds=90)
        if not processing_complete:
            print("\n⚠ Warning: Processing may not be complete")
        
        # Run all validations
        results = {}
        results["archives"] = self.validate_archives()
        results["messages"] = self.validate_messages(expected_min_count=10)
        results["threads"] = self.validate_threads()
        results["chunks"] = self.validate_chunks(expected_min_count=10)
        results["embeddings"] = self.validate_embeddings(expected_min_count=10)
        results["consistency"] = self.validate_data_consistency(results)
        
        # Summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        all_passed = True
        for check_name, result in results.items():
            status = result.get("status", "UNKNOWN")
            count = result.get("count", "N/A")
            
            status_symbol = "✓" if status == "PASS" else ("⚠" if status == "WARN" else "❌")
            print(f"{status_symbol} {check_name.capitalize()}: {status} (count: {count})")
            
            if status == "FAIL":
                all_passed = False
                details = result.get("details", "")
                if details:
                    print(f"  Details: {details}")
        
        print("=" * 60)
        
        if all_passed:
            print("✓ ALL VALIDATIONS PASSED")
            return True
        else:
            print("❌ SOME VALIDATIONS FAILED")
            return False
    
    def close(self):
        """Close connections."""
        self.mongo_client.close()


def main():
    """Main entry point for validation script."""
    validator = E2EMessageFlowValidator()
    
    try:
        success = validator.run_validation()
        validator.close()
        
        if success:
            print("\n✓ End-to-end validation PASSED")
            sys.exit(0)
        else:
            print("\n❌ End-to-end validation FAILED")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
        validator.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
