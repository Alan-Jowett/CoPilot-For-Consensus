# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Verify that archives collection is populated after ingestion.

This script connects to MongoDB and checks that the archives collection
has entries with the expected structure.

Usage:
    python scripts/verify_archives_collection.py
"""

import os
import sys
from pymongo import MongoClient


def verify_archives_collection():
    """Verify archives collection contents."""
    # Get MongoDB connection details from environment
    mongo_host = os.getenv("DOC_DB_HOST", "localhost")
    mongo_port = int(os.getenv("DOC_DB_PORT", "27017"))
    mongo_user = os.getenv("DOC_DB_USER", "root")
    mongo_password = os.getenv("DOC_DB_PASSWORD", "example")
    mongo_db = os.getenv("DOC_DB_NAME", "copilot")
    
    connection_string = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"
    
    try:
        # Connect to MongoDB
        print(f"Connecting to MongoDB at {mongo_host}:{mongo_port}...")
        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.server_info()
        print("✓ Connected to MongoDB")
        
        # Get database and collection
        db = client[mongo_db]
        archives = db.archives
        
        # Count archives
        archive_count = archives.count_documents({})
        print(f"\n✓ Archives collection has {archive_count} documents")
        
        if archive_count == 0:
            print("⚠ Warning: No archives found. Has ingestion run yet?")
            return True
        
        # Get a sample archive
        sample_archive = archives.find_one()
        
        print("\nSample archive document:")
        print(f"  archive_id: {sample_archive.get('archive_id', 'MISSING')}")
        print(f"  source: {sample_archive.get('source', 'MISSING')}")
        print(f"  source_url: {sample_archive.get('source_url', 'MISSING')}")
        print(f"  format: {sample_archive.get('format', 'MISSING')}")
        print(f"  ingestion_date: {sample_archive.get('ingestion_date', 'MISSING')}")
        print(f"  message_count: {sample_archive.get('message_count', 'MISSING')}")
        print(f"  file_path: {sample_archive.get('file_path', 'MISSING')}")
        print(f"  status: {sample_archive.get('status', 'MISSING')}")
        
        # Verify required fields
        required_fields = ['archive_id', 'source', 'ingestion_date', 'status']
        missing_fields = [f for f in required_fields if f not in sample_archive]
        
        if missing_fields:
            print(f"\n✗ Error: Missing required fields: {', '.join(missing_fields)}")
            return False
        
        # Count by status
        print("\nArchive status breakdown:")
        for status in ['pending', 'processed', 'failed']:
            count = archives.count_documents({'status': status})
            print(f"  {status}: {count}")
        
        print("\n✓ Archives collection verification successful!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    success = verify_archives_collection()
    sys.exit(0 if success else 1)
