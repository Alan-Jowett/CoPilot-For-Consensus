# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion Service: Fetch mailing list archives from various sources."""

import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from copilot_events import create_publisher
from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector

from app import __version__
from app.config import IngestionConfig
from app.service import IngestionService

# Bootstrap logger before configuration is loaded
logger = create_logger(name="ingestion-bootstrap")


def main():
    """Main entry point for the ingestion service."""
    logger.info("Starting Ingestion Service", version=__version__)

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
                logger.info("Loaded configuration from file", config_file=config_file)
            except Exception as e:
                logger.warning(
                    "Failed to load config file, using environment variables",
                    config_file=config_file,
                    error=str(e),
                )
        else:
            logger.info(
                "No config file found, using environment variables",
                expected_path=config_file,
            )

        # Recreate logger with configured settings
        logger = create_logger(
            logger_type=config.log_type,
            level=config.log_level,
            name=config.logger_name,
        )
        metrics = create_metrics_collector(backend=config.metrics_backend)

        logger.info(
            "Logger configured",
            log_level=config.log_level,
            log_type=config.log_type,
            metrics_backend=config.metrics_backend,
        )

        # Ensure storage path exists
        config.ensure_storage_path()
        logger.info("Storage path prepared", storage_path=config.storage_path)

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
            logger.warning(
                "Failed to connect to message bus. Will continue with noop publisher.",
                host=config.message_bus_host,
                port=config.message_bus_port,
            )

        # Create ingestion service
        service = IngestionService(
            config,
            publisher,
            logger=logger,
            metrics=metrics,
        )

        # Ingest from all enabled sources
        logger.info(
            "Starting ingestion for enabled sources",
            enabled_source_count=len(config.get_enabled_sources()),
        )

        results = service.ingest_all_enabled_sources()

        # Log results
        for source_name, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            logger.info("Source ingestion summary", source_name=source_name, status=status)

        # Count successes
        successful = sum(1 for s in results.values() if s)
        logger.info(
            "Ingestion complete",
            successful_sources=successful,
            total_sources=len(results),
        )

        # Cleanup
        publisher.disconnect()

        # Exit with appropriate code
        sys.exit(0 if successful == len(results) else 1)

    except Exception as e:
        logger.error("Fatal error in ingestion service", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
