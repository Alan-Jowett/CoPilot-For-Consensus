# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Ingestion service: Fetch mailing list archives."""
    logger.info("Starting Ingestion Service")
    storage_path = os.getenv("STORAGE_PATH", "/data/raw_archives")
    logger.info(f"Storage path: {storage_path}")
    
    # Keep service running
    while True:
        logger.info("Ingestion service running...")
        time.sleep(30)

if __name__ == "__main__":
    main()
