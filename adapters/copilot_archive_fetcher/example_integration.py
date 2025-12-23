# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of copilot-archive-fetcher in ingestion pipeline."""

import logging
from copilot_archive_fetcher import (
    create_fetcher,
    SourceConfig,
    UnsupportedSourceTypeError,
)

logger = logging.getLogger(__name__)


def fetch_and_process_archive(config_dict: dict, output_dir: str) -> dict:
    """
    Example function showing how to use archive fetcher in ingestion service.

    Args:
        config_dict: Dictionary with source configuration
        output_dir: Directory to store fetched files

    Returns:
        Dictionary with fetch results
    """
    try:
        # Create source configuration from dictionary
        # (e.g., loaded from environment variables or config file)
        config = SourceConfig(
            name=config_dict.get("name"),
            source_type=config_dict.get("type"),
            url=config_dict.get("url"),
            port=config_dict.get("port"),
            username=config_dict.get("username"),
            password=config_dict.get("password"),
            folder=config_dict.get("folder"),
        )

        logger.info(f"Fetching archive from source: {config.name} ({config.source_type})")

        # Create appropriate fetcher using factory pattern
        fetcher = create_fetcher(config)

        # Fetch the archive
        success, files, error = fetcher.fetch(output_dir)

        if success:
            logger.info(f"Successfully fetched {len(files)} files from {config.name}")
            return {
                "success": True,
                "source_name": config.name,
                "file_count": len(files),
                "files": files,
                "output_dir": output_dir,
            }
        else:
            logger.error(f"Failed to fetch from {config.name}: {error}")
            return {
                "success": False,
                "source_name": config.name,
                "error": error,
            }

    except UnsupportedSourceTypeError as e:
        logger.error(f"Unsupported source type: {e}")
        return {
            "success": False,
            "error": f"Unsupported source type: {e}",
        }
    except Exception as e:
        logger.error(f"Unexpected error during archive fetch: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {e}",
        }


def main():
    """Example: Process multiple archive sources."""

    # Example configuration sources
    sources = [
        {
            "name": "http-archive",
            "type": "http",
            "url": "https://example.com/archive.tar.gz",
        },
        {
            "name": "local-files",
            "type": "local",
            "url": "/data/source/files",
        },
        {
            "name": "rsync-mirror",
            "type": "rsync",
            "url": "rsync://mirror.example.com/data/",
        },
    ]

    output_dir = "/tmp/archives"
    results = []

    for source_config in sources:
        result = fetch_and_process_archive(source_config, output_dir)
        results.append(result)

        if result["success"]:
            print(f"✓ {result['source_name']}: {result['file_count']} files fetched")
        else:
            print(f"✗ {result['source_name']}: {result['error']}")

    # Summary
    successful = sum(1 for r in results if r.get("success"))
    print(f"\nSummary: {successful}/{len(results)} sources fetched successfully")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
