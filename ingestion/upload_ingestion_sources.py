# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Upload ingestion sources from a JSON config into the document store.

Assumptions:
- Runs inside the ingestion container.
- Uses adapters only: copilot_config for config loading, copilot_storage for document store.
- Document store location is determined via ingestion config/env handled by adapters.
"""

import os
import json
import sys
import logging
from pathlib import Path

# Prefer adapters package
try:
    from copilot_config import load_config
    from copilot_storage import create_document_store
except ImportError:
    print("Error: copilot_storage adapter not available. Ensure adapters are installed.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upload_ingestion_sources")


def get_store():
    """Create a document store resolved via ingestion config using adapters.

    - Relies on copilot_config to load the ingestion schema and any env.
    - Uses copilot_storage factory to obtain the store (type/env decided externally).
    """
    # Load ingestion config to ensure schema/validation and any adapter side-effects
    try:
        _ = load_config("ingestion")
    except Exception as e:
        logger.warning("Proceeding without loaded config; using storage defaults. Error: %s", e)

    # Let storage adapter decide store type from environment/container config
    return create_document_store()


def main(config_path: Path):
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    sources = cfg.get("sources", [])
    if not isinstance(sources, list) or not sources:
        logger.error("No sources found in config JSON under 'sources'.")
        sys.exit(1)

    store = get_store()
    if not store.connect():
        logger.error("Failed to connect to document store.")
        sys.exit(1)

    inserted = 0
    for src in sources:
        # Basic validation aligned with ingestion schema
        required = ["name", "source_type", "url", "enabled"]
        if not all(k in src for k in required):
            logger.warning("Skipping invalid source missing required fields: %s", src)
            continue
        store.insert_document("sources", src)
        inserted += 1

    logger.info("Inserted %d sources into document store.", inserted)
    store.disconnect()


if __name__ == "__main__":
    # Default to ingestion/config.test.json
    cfg_path_str = sys.argv[1] if len(sys.argv) > 1 else os.path.join("ingestion", "config.test.json")
    main(Path(cfg_path_str))
