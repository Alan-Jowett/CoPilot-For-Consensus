# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example demonstrating schema-driven configuration system.

This example shows how to:
1. Define a configuration schema
2. Load configuration from environment variables
3. Access configuration with type safety
4. Handle validation errors
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from copilot_config import (
    load_typed_config,
    ConfigValidationError,
    ConfigSchemaError,
    EnvConfigProvider,
)

# Find the schemas directory
def get_schema_dir():
    """Find the schemas directory."""
    current = Path(__file__).parent
    for _ in range(5):  # Search up to 5 levels up
        schema_dir = current / "schemas"
        if schema_dir.exists():
            return str(schema_dir)
        current = current.parent
    # Fall back to environment variable or current directory
    return os.environ.get("SCHEMA_DIR", "./schemas")

SCHEMA_DIR = get_schema_dir()


def example_basic_loading():
    """Example 1: Basic configuration loading."""
    print("=" * 60)
    print("Example 1: Basic Configuration Loading")
    print("=" * 60)
    
    # Set up environment variables for demonstration
    os.environ["MESSAGE_BUS_HOST"] = "rabbitmq.example.com"
    os.environ["MESSAGE_BUS_PORT"] = "5672"
    
    try:
        # Load configuration from schema (type-safe)
        config = load_typed_config("chunking", schema_dir=SCHEMA_DIR)
        
        print(f"✓ Configuration loaded successfully!")
        print(f"  Message Bus Host: {config.message_bus_host}")
        print(f"  Message Bus Port: {config.message_bus_port}")
        print(f"  Document Store Type: {config.doc_store_type}")
        print(f"  Chunk Size: {config.chunk_size}")
        print()
        
    except ConfigSchemaError as e:
        print(f"✗ Schema error: {e}")
    except ConfigValidationError as e:
        print(f"✗ Validation error: {e}")


def example_typed_config():
    """Example 2: Typed configuration with attribute access."""
    print("=" * 60)
    print("Example 2: Typed Configuration")
    print("=" * 60)
    
    # Set up environment
    os.environ["MESSAGE_BUS_HOST"] = "messagebus"
    os.environ["DOCUMENT_DATABASE_HOST"] = "mongodb.example.com"
    
    try:
        # Load typed configuration
        config = load_typed_config(
            "chunking",
            schema_dir=SCHEMA_DIR
        )
        
        print(f"✓ Typed configuration loaded!")
        
        # Access via attributes only (dict-style not supported for verification)
        print(f"  Message Bus Host: {config.message_bus_host}")
        print(f"  Message Bus Port: {config.message_bus_port}")
        print(f"  Document Store Host: {config.doc_store_host}")
        print(f"  Document Store Type: {config.doc_store_type}")
        print()
        
    except Exception as e:
        print(f"✗ Error: {e}")


def example_validation_errors():
    """Example 3: Handling validation errors."""
    print("=" * 60)
    print("Example 3: Validation Error Handling")
    print("=" * 60)
    
    # Note: In the chunking schema, all required fields have defaults,
    # so validation won't fail for missing values.
    # This demonstrates what happens when validation passes.
    
    # Create a custom environment provider with minimal config
    env_provider = EnvConfigProvider(environ={
        # Only providing a subset - others will use defaults
        "MESSAGE_BUS_PORT": "5672"
    })
    
    try:
        config = load_typed_config(
            "chunking",
            schema_dir=SCHEMA_DIR,
            env_provider=env_provider
        )
        print(f"✓ Configuration loaded successfully!")
        print(f"  Note: Required fields with defaults don't cause validation errors")
        print(f"  Message Bus Host (from default): {config.message_bus_host}")
        print(f"  Message Bus Port (from env): {config.message_bus_port}")
        print()
        
    except ConfigValidationError as e:
        print(f"✗ Validation error (unexpected):")
        print(f"  {e}")
        print()


def example_default_values():
    """Example 4: Default values from schema."""
    print("=" * 60)
    print("Example 4: Default Values")
    print("=" * 60)
    
    # Provide only required fields
    env_provider = EnvConfigProvider(environ={
        "MESSAGE_BUS_HOST": "messagebus",
        "DOCUMENT_DATABASE_HOST": "documentdb",
    })
    
    try:
        config = load_typed_config(
            "chunking",
            schema_dir=SCHEMA_DIR,
            env_provider=env_provider
        )
        
        print(f"✓ Configuration loaded with defaults!")
        print(f"  Message Bus Host (provided): {config.message_bus_host}")
        print(f"  Message Bus Port (default): {config.message_bus_port}")
        print(f"  Chunk Size (default): {config.chunk_size}")
        print(f"  Chunk Overlap (default): {config.chunk_overlap}")
        print(f"  Chunking Strategy (default): {config.chunking_strategy}")
        print()
        
    except Exception as e:
        print(f"✗ Error: {e}")


def example_type_conversion():
    """Example 5: Type conversion."""
    print("=" * 60)
    print("Example 5: Type Conversion")
    print("=" * 60)
    
    # Provide values as strings
    env_provider = EnvConfigProvider(environ={
        "MESSAGE_BUS_HOST": "messagebus",
        "MESSAGE_BUS_PORT": "9999",  # String will be converted to int
        "DOCUMENT_DATABASE_HOST": "documentdb",
        "DOCUMENT_DATABASE_PORT": "27017",
        "CHUNK_SIZE": "1024",
        "CHUNK_OVERLAP": "100",
    })
    
    try:
        config = load_typed_config(
            "chunking",
            schema_dir=SCHEMA_DIR,
            env_provider=env_provider
        )
        
        print(f"✓ Type conversion successful!")
        print(f"  Message Bus Port: {config.message_bus_port} (type: {type(config.message_bus_port).__name__})")
        print(f"  Document Store Port: {config.doc_store_port} (type: {type(config.doc_store_port).__name__})")
        print(f"  Chunk Size: {config.chunk_size} (type: {type(config.chunk_size).__name__})")
        print()
        
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  Schema-Driven Configuration System Examples".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")
    
    example_basic_loading()
    example_typed_config()
    example_validation_errors()
    example_default_values()
    example_type_conversion()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
