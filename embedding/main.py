# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
import time
import logging

from embedding.factory import create_embedding_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Embedding service: Convert chunks into vector embeddings."""
    logger.info("Starting Embedding Service")
    vector_db_host = os.getenv("VECTOR_DB_HOST", "localhost")
    logger.info(f"Vector DB host: {vector_db_host}")
    
    # Initialize embedding provider
    try:
        embedding_provider = create_embedding_provider()
        logger.info(f"Embedding provider initialized: {type(embedding_provider).__name__}")
        
        # Test embedding generation
        test_text = "This is a test message for embedding generation."
        embedding = embedding_provider.embed(test_text)
        logger.info(f"Generated test embedding with dimension: {len(embedding)}")
    except Exception as e:
        logger.error(f"Failed to initialize embedding provider: {e}")
        logger.info("Service will continue but embeddings may not be available")
    
    # Keep service running
    while True:
        logger.info("Embedding service running...")
        time.sleep(30)

if __name__ == "__main__":
    main()
