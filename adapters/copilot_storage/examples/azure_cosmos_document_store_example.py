#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the AzureCosmosDocumentStore.

This script demonstrates how to use the AzureCosmosDocumentStore
to interact with Azure Cosmos DB for document storage.
"""

import os
from copilot_storage import (
    create_document_store,
    DocumentStoreConnectionError,
    DocumentNotFoundError,
    DocumentValidationError,
    ValidatingDocumentStore,
)


def main():
    """Demonstrate Azure Cosmos DB document store functionality."""
    
    print("=" * 60)
    print("AzureCosmosDocumentStore Examples")
    print("=" * 60)
    print()
    
    # Example 1: Basic connection and document operations
    print("Example 1: Basic Connection and Operations")
    print("-" * 60)
    
    # Get configuration from environment variables
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    
    if not endpoint or not key:
        print("✗ Azure Cosmos DB credentials are not configured.")
        print()
        print("Please set the following environment variables before running this example:")
        print("  - COSMOS_ENDPOINT: Your Cosmos DB endpoint URL")
        print("  - COSMOS_KEY: Your Cosmos DB account key")
        print()
        return
    
    # Create the store using the factory
    try:
        store = create_document_store(
            store_type="azurecosmos",
            endpoint=endpoint,
            key=key,
            database="copilot_demo",
            container="documents",
            partition_key="/collection"
        )
        
        # Connect to Cosmos DB
        store.connect()
        print(f"✓ Connected to Azure Cosmos DB at {endpoint}")
        print()
        
        # Example 2: Insert documents
        print("Example 2: Inserting Documents")
        print("-" * 60)
        
        user_doc = {
            "name": "Alice Smith",
            "email": "alice@example.com",
            "age": 30,
            "department": "Engineering"
        }
        
        doc_id = store.insert_document("users", user_doc)
        print(f"✓ Inserted user document with ID: {doc_id}")
        print()
        
        # Example 3: Retrieve document
        print("Example 3: Retrieving Documents")
        print("-" * 60)
        
        retrieved = store.get_document("users", doc_id)
        if retrieved:
            print(f"✓ Retrieved document:")
            print(f"   Name: {retrieved['name']}")
            print(f"   Email: {retrieved['email']}")
            print(f"   Age: {retrieved['age']}")
        else:
            print("✗ Document not found")
        print()
        
        # Example 4: Query documents
        print("Example 4: Querying Documents")
        print("-" * 60)
        
        # Insert more documents for querying
        store.insert_document("users", {"name": "Bob Jones", "age": 25, "department": "Sales"})
        store.insert_document("users", {"name": "Charlie Brown", "age": 30, "department": "Marketing"})
        
        # Query by age
        results = store.query_documents("users", {"age": 30}, limit=10)
        print(f"✓ Found {len(results)} users with age 30:")
        for user in results:
            print(f"   - {user['name']}")
        print()
        
        # Example 5: Update document
        print("Example 5: Updating Documents")
        print("-" * 60)
        
        store.update_document("users", doc_id, {"age": 31, "department": "Senior Engineering"})
        
        updated = store.get_document("users", doc_id)
        print(f"✓ Updated document:")
        print(f"   Name: {updated['name']}")
        print(f"   Age: {updated['age']}")
        print(f"   Department: {updated['department']}")
        print()
        
        # Example 6: Aggregation
        print("Example 6: Aggregation Queries")
        print("-" * 60)
        
        pipeline = [
            {"$match": {"department": "Engineering"}},
            {"$limit": 10}
        ]
        
        results = store.aggregate_documents("users", pipeline)
        print(f"✓ Found {len(results)} engineers:")
        for user in results:
            print(f"   - {user['name']}")
        print()
        
        # Example 7: Delete document
        print("Example 7: Deleting Documents")
        print("-" * 60)
        
        store.delete_document("users", doc_id)
        print(f"✓ Deleted document with ID: {doc_id}")
        
        # Verify deletion
        deleted = store.get_document("users", doc_id)
        if deleted is None:
            print("✓ Document confirmed deleted")
        print()
        
        # Example 8: Error handling
        print("Example 8: Error Handling")
        print("-" * 60)
        
        try:
            store.get_document("users", "nonexistent_id")
            print("✓ Handled non-existent document gracefully (returned None)")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        
        try:
            store.delete_document("users", "nonexistent_id")
            print("✗ Should have raised DocumentNotFoundError")
        except DocumentNotFoundError:
            print("✓ Correctly raised DocumentNotFoundError for delete")
        print()
        
        # Example 9: Complex documents
        print("Example 9: Complex Nested Documents")
        print("-" * 60)
        
        project_doc = {
            "project_name": "Copilot for Consensus",
            "team": {
                "lead": "Alice Smith",
                "members": ["Bob Jones", "Charlie Brown", "Diana Prince"],
                "size": 4
            },
            "milestones": [
                {"name": "Alpha", "date": "2025-01-15", "completed": True},
                {"name": "Beta", "date": "2025-02-15", "completed": False},
                {"name": "GA", "date": "2025-03-15", "completed": False}
            ],
            "metadata": {
                "created": "2025-01-01",
                "last_updated": "2025-01-20",
                "tags": ["ai", "consensus", "open-source"]
            }
        }
        
        project_id = store.insert_document("projects", project_doc)
        print(f"✓ Inserted complex project document with ID: {project_id}")
        
        retrieved_project = store.get_document("projects", project_id)
        print(f"   Project: {retrieved_project['project_name']}")
        print(f"   Team Lead: {retrieved_project['team']['lead']}")
        print(f"   Team Size: {retrieved_project['team']['size']}")
        print(f"   Milestones: {len(retrieved_project['milestones'])}")
        print()
        
        # Clean up
        store.delete_document("projects", project_id)
        
        # Disconnect
        store.disconnect()
        print("✓ Disconnected from Azure Cosmos DB")
        print()
        
    except DocumentStoreConnectionError as e:
        print(f"✗ Connection error: {e}")
        print()
        print("Make sure to set the following environment variables:")
        print("  - COSMOS_ENDPOINT: Your Cosmos DB endpoint URL")
        print("  - COSMOS_KEY: Your Cosmos DB account key")
        print()
        return
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return
    
    # Example 10: Using with ValidatingDocumentStore
    print("Example 10: Using with ValidatingDocumentStore")
    print("-" * 60)
    print()
    
    # Create a simple schema provider
    class SimpleSchemaProvider:
        def __init__(self):
            self.schemas = {
                "User": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "age": {"type": "integer", "minimum": 0, "maximum": 150}
                    },
                    "required": ["name", "email"],
                    "additionalProperties": True  # Allow extra fields like collection, id
                }
            }
        
        def get_schema(self, schema_name):
            return self.schemas.get(schema_name)
    
    try:
        # Create base store
        base_store = create_document_store(
            store_type="azurecosmos",
            endpoint=endpoint,
            key=key,
            database="copilot_demo",
            container="documents"
        )
        base_store.connect()
        
        # Wrap with validation
        schema_provider = SimpleSchemaProvider()
        validating_store = ValidatingDocumentStore(
            store=base_store,
            schema_provider=schema_provider,
            strict=True,
            validate_reads=False
        )
        
        # Valid document
        valid_user = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 35
        }
        
        doc_id = validating_store.insert_document("user", valid_user)
        print(f"✓ Inserted validated user with ID: {doc_id}")
        
        # Invalid document
        invalid_user = {
            "name": "Jane Doe",
            # Missing required email field
            "age": 28
        }
        
        try:
            validating_store.insert_document("user", invalid_user)
            print("✗ Should have raised DocumentValidationError")
        except DocumentValidationError as e:
            print(f"✓ Validation correctly rejected invalid document:")
            print(f"   Errors: {e.errors}")
        
        # Clean up
        validating_store.delete_document("user", doc_id)
        base_store.disconnect()
        print()
        
    except DocumentStoreConnectionError:
        print("⚠ Skipping ValidatingDocumentStore example (connection failed)")
        print()
    except Exception as e:
        print(f"✗ Unexpected error in validation example: {e}")
        print()
    
    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print()
    print("Deployment Considerations for Azure Cosmos DB:")
    print("- Throughput: Configure appropriate RU/s for your workload")
    print("- Indexing: Customize indexing policy for query performance")
    print("- Partitioning: Use /collection as partition key for multi-tenant scenarios")
    print("- Consistency: Choose consistency level based on requirements")
    print("- Backup: Enable automatic backups for production")
    print("- Security: Use managed identity instead of account keys when possible")
    print()


if __name__ == "__main__":
    main()
