# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Fetch mailing list archives from various sources."""

import logging
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import __version__
from app.config import IngestionConfig
from app.event_publisher import create_publisher
from app.service import IngestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the ingestion service."""
    logger.info(f"Starting Ingestion Service (version {__version__})")

    try:
        # Load configuration from environment and optional config file
        config = IngestionConfig.from_env()

        # Try to load from config file if it exists
        # Check both /app/config.yaml (Docker) and ./config.yaml (local development)
        config_file = os.getenv("CONFIG_FILE")
        if not config_file:
            if os.path.exists("/app/config.yaml"):
                config_file = "/app/config.yaml"
            elif os.path.exists("config.yaml"):
                config_file = "config.yaml"
            else:
                config_file = "/app/config.yaml"  # Default to Docker path
        
        if os.path.exists(config_file):
            try:
                config = IngestionConfig.from_yaml_file(config_file)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(
                    f"Failed to load config file {config_file}: {e}. Using environment variables."
                )
        else:
            logger.info(f"No config file found at {config_file}, using environment variables")

        # Set logging level
        logging.getLogger().setLevel(config.log_level)
        logger.info(f"Log level set to {config.log_level}")

        # Ensure storage path exists
        config.ensure_storage_path()
        logger.info(f"Storage path: {config.storage_path}")

        # Create event publisher
        publisher = create_publisher(
            message_bus_type=config.message_bus_type,
            host=config.message_bus_host,
            port=config.message_bus_port,
            username=config.message_bus_user,
            password=config.message_bus_password,
        )

        # Connect publisher
        if not publisher.connect():
            logger.warning("Failed to connect to message bus. Will continue with noop publisher.")

        # Create ingestion service
        service = IngestionService(config, publisher)

        # Ingest from all enabled sources
        logger.info(f"Found {len(config.get_enabled_sources())} enabled source(s)")

        results = service.ingest_all_enabled_sources()

        # Log results
        for source_name, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            logger.info(f"Source '{source_name}': {status}")

        # Count successes
        successful = sum(1 for s in results.values() if s)
        logger.info(f"Ingestion complete: {successful}/{len(results)} sources succeeded")

        # Cleanup
        publisher.disconnect()

        # Exit with appropriate code
        sys.exit(0 if successful == len(results) else 1)

    except Exception as e:
        logger.error(f"Fatal error in ingestion service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
