# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import time
import logging
from copilot_config import create_config_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Parsing service: Convert raw .mbox files into structured JSON."""
    logger.info("Starting Parsing Service")
    
    # Use ConfigProvider for configuration
    config = create_config_provider()
    storage_path = config.get("STORAGE_PATH", "/data/parsed_json")
    
    logger.info(f"Storage path: {storage_path}")
    
    # Keep service running
    while True:
        logger.info("Parsing service running...")
        time.sleep(30)

if __name__ == "__main__":
    main()
