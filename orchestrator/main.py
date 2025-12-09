# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Orchestration service: Coordinate summarization and analysis tasks."""
    logger.info("Starting Orchestration Service")
    vector_db_host = os.getenv("VECTOR_DB_HOST", "localhost")
    doc_db_host = os.getenv("DOC_DB_HOST", "localhost")
    logger.info(f"Vector DB host: {vector_db_host}")
    logger.info(f"Document DB host: {doc_db_host}")
    
    # Keep service running
    while True:
        logger.info("Orchestration service running...")
        time.sleep(30)

if __name__ == "__main__":
    main()
