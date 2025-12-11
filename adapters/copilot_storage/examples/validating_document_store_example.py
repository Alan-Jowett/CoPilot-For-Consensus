#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the ValidatingDocumentStore.

This script demonstrates how to use the ValidatingDocumentStore
to enforce schema validation on document operations.
"""

from copilot_storage import (
    create_document_store,
    ValidatingDocumentStore,
    DocumentValidationError,
)


class SimpleSchemaProvider:
    """Simple schema provider for demonstration purposes."""
    
    def __init__(self):
        """Initialize with example schemas."""
        self.schemas = {
            "User": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "age": {"type": "integer", "minimum": 0, "maximum": 150}
                },
                "required": ["user_id", "name", "email"],
                "additionalProperties": False
            },
            "Product": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "name": {"type": "string"},
                    "price": {"type": "number", "minimum": 0},
                    "in_stock": {"type": "boolean"}
                },
                "required": ["product_id", "name", "price"],
                "additionalProperties": False
            }
        }
    
    def get_schema(self, schema_name: str):
        """Return schema for schema name or None if not found."""
        return self.schemas.get(schema_name)


def main():
    """Demonstrate validating document store functionality."""
    
    print("=" * 60)
    print("ValidatingDocumentStore Examples")
    print("=" * 60)
    print()
    
    # Create base document store (using in-memory for this example)
    base_store = create_document_store("inmemory")
    base_store.connect()
    
    # Create schema provider
    schema_provider = SimpleSchemaProvider()
    
    # Example 1: Strict mode with valid document
    print("Example 1: Inserting valid document in strict mode")
    print("-" * 60)
    
    validating_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider,
        strict=True,
        validate_reads=False
    )
    
    valid_user = {
        "user_id": "user-123",
        "name": "Alice Smith",
        "email": "alice@example.com",
        "age": 30
    }
    
    try:
        doc_id = validating_store.insert_document("user", valid_user)
        print(f"✓ Document inserted successfully with ID: {doc_id}")
    except DocumentValidationError as e:
        print(f"✗ Validation failed: {e}")
    print()
    
    # Example 2: Strict mode with invalid document
    print("Example 2: Inserting invalid document in strict mode (will fail)")
    print("-" * 60)
    
    invalid_user = {
        "user_id": "user-456",
        "name": "Bob Jones",
        # Missing required field: email
        "age": 25
    }
    
    try:
        doc_id = validating_store.insert_document("user", invalid_user)
        print(f"✓ Document inserted successfully with ID: {doc_id}")
    except DocumentValidationError as e:
        print(f"✗ Validation failed (as expected):")
        print(f"   Collection: {e.collection}")
        print(f"   Errors:")
        for error in e.errors:
            print(f"     - {error}")
    print()
    
    # Example 3: Non-strict mode with invalid document
    print("Example 3: Inserting invalid document in non-strict mode (will succeed)")
    print("-" * 60)
    
    permissive_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider,
        strict=False,
        validate_reads=False
    )
    
    try:
        doc_id = permissive_store.insert_document("user", invalid_user)
        print(f"✓ Document inserted despite validation errors with ID: {doc_id}")
        print("   (Warnings logged, but insert proceeded)")
    except DocumentValidationError as e:
        print(f"✗ Unexpected validation error: {e}")
    print()
    
    # Example 4: Collection name to schema name conversion
    print("Example 4: Collection name to schema name conversion")
    print("-" * 60)
    
    product = {
        "product_id": "prod-789",
        "name": "Widget",
        "price": 19.99,
        "in_stock": True
    }
    
    try:
        # Collection "product" maps to schema "Product"
        doc_id = validating_store.insert_document("product", product)
        print(f"✓ Product inserted with ID: {doc_id}")
        print(f"   Collection 'product' → Schema 'Product'")
    except DocumentValidationError as e:
        print(f"✗ Validation failed: {e}")
    print()
    
    # Example 5: Validating reads (debug mode)
    print("Example 5: Validating reads in debug mode")
    print("-" * 60)
    
    debug_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider,
        strict=True,
        validate_reads=True  # Enable read validation
    )
    
    # Insert a valid document first
    valid_product = {
        "product_id": "prod-999",
        "name": "Gadget",
        "price": 29.99,
        "in_stock": False
    }
    doc_id = base_store.insert_document("product", valid_product)
    print(f"Inserted product with ID: {doc_id}")
    
    # Try to read it back (should validate on read)
    try:
        retrieved = debug_store.get_document("product", doc_id)
        if retrieved:
            print(f"✓ Retrieved and validated document: {retrieved['name']}")
        else:
            print("✗ Document not found")
    except DocumentValidationError as e:
        print(f"✗ Read validation failed: {e}")
    print()
    
    # Example 6: Updating documents with validation
    print("Example 6: Updating documents with validation")
    print("-" * 60)
    
    valid_update = {"price": 24.99}
    invalid_update = {"price": "not a number"}
    
    # Valid update
    try:
        result = validating_store.update_document("product", doc_id, valid_update)
        print(f"✓ Document updated successfully: {result}")
    except DocumentValidationError as e:
        print(f"✗ Update validation failed: {e}")
    
    # Invalid update
    try:
        result = validating_store.update_document("product", doc_id, invalid_update)
        print(f"✓ Document updated successfully: {result}")
    except DocumentValidationError as e:
        print(f"✗ Update validation failed (as expected):")
        for error in e.errors:
            print(f"     - {error}")
    print()
    
    # Example 7: Querying and deleting (no validation)
    print("Example 7: Querying and deleting documents")
    print("-" * 60)
    
    # Query doesn't validate
    products = validating_store.query_documents("product", {"in_stock": True})
    print(f"Found {len(products)} products in stock")
    
    # Delete doesn't validate
    result = validating_store.delete_document("product", doc_id)
    print(f"Document deleted: {result}")
    print()
    
    # Example 8: Without schema provider
    print("Example 8: Operating without schema provider (no validation)")
    print("-" * 60)
    
    no_validation_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=None,
        strict=True
    )
    
    arbitrary_doc = {
        "anything": "goes",
        "no": "validation",
        "at_all": 42
    }
    
    try:
        doc_id = no_validation_store.insert_document("arbitrary_collection", arbitrary_doc)
        print(f"✓ Document inserted without validation with ID: {doc_id}")
    except DocumentValidationError as e:
        print(f"✗ Unexpected validation error: {e}")
    print()
    
    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
    
    base_store.disconnect()


if __name__ == "__main__":
    main()
