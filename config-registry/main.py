# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Config Registry Service: REST API and subscription management."""

import os
import sys
from typing import Any

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from app import __version__
from app.models import ConfigDiff, ConfigDocument, ConfigUpdate
from app.service import ConfigRegistryService
from copilot_config import load_typed_config
from copilot_events import create_publisher
from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_storage import create_document_store
from fastapi import FastAPI, HTTPException, Query

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="config-registry")

# Create FastAPI app
app = FastAPI(
    title="Config Registry Service",
    version=__version__,
    description="Centralized configuration management with hot-reload support",
)

# Global service instance
registry_service: ConfigRegistryService | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    global registry_service

    logger.info("startup_begin", version=__version__)

    try:
        # Load configuration
        config = load_typed_config("config-registry")

        # Initialize document store
        doc_store = create_document_store(
            store_type=config.doc_store_type,
            host=config.doc_store_host,
            port=config.doc_store_port,
            database=config.doc_store_name,
            username=config.doc_store_user,
            password=config.doc_store_password,
        )
        doc_store.connect()

        # Initialize event publisher for notifications
        event_publisher = None
        if hasattr(config, "message_bus_type"):
            event_publisher = create_publisher(
                bus_type=config.message_bus_type,
                host=config.message_bus_host,
                port=config.message_bus_port,
                username=config.message_bus_user,
                password=config.message_bus_password,
            )
            event_publisher.connect()

        # Create registry service
        registry_service = ConfigRegistryService(
            doc_store=doc_store, event_publisher=event_publisher, logger=logger
        )

        logger.info("startup_complete", version=__version__)

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("shutdown_begin")
    # Cleanup resources if needed
    logger.info("shutdown_complete")


@app.get("/health")
def health():
    """Health check endpoint."""
    stats = registry_service.get_stats() if registry_service else {}

    return {
        "status": "healthy",
        "service": "config-registry",
        "version": __version__,
        "configs_created": stats.get("configs_created", 0),
        "configs_updated": stats.get("configs_updated", 0),
        "configs_retrieved": stats.get("configs_retrieved", 0),
        "notifications_sent": stats.get("notifications_sent", 0),
    }


@app.get("/stats")
def stats():
    """Get service statistics."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return registry_service.get_stats()


# Configuration CRUD endpoints


@app.get("/api/configs")
def list_configs(
    service_name: str | None = Query(None, description="Filter by service name"),
    environment: str | None = Query(None, description="Filter by environment"),
) -> list[dict[str, Any]]:
    """List all configurations (latest versions only)."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return registry_service.list_configs(service_name, environment)


@app.get("/api/configs/{service_name}")
def get_config(
    service_name: str,
    environment: str = Query("default", description="Environment name"),
    version: int | None = Query(None, description="Specific version (defaults to latest)"),
) -> dict[str, Any]:
    """Get configuration for a service."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    config = registry_service.get_config(service_name, environment, version)
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return config


@app.post("/api/configs/{service_name}", status_code=201)
def create_config(service_name: str, update: ConfigUpdate, environment: str = "default") -> ConfigDocument:
    """Create a new configuration."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return registry_service.create_config(
            service_name=service_name,
            config_data=update.config_data,
            environment=environment,
            created_by=update.created_by,
            comment=update.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/configs/{service_name}")
def update_config(service_name: str, update: ConfigUpdate, environment: str = "default") -> ConfigDocument:
    """Update configuration (creates new version)."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return registry_service.update_config(
            service_name=service_name,
            config_data=update.config_data,
            environment=environment,
            created_by=update.created_by,
            comment=update.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/configs/{service_name}")
def delete_config(
    service_name: str,
    environment: str = Query("default", description="Environment name"),
    version: int | None = Query(None, description="Specific version (if None, deletes all)"),
) -> dict[str, Any]:
    """Delete configuration(s)."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    count = registry_service.delete_config(service_name, environment, version)
    return {"deleted": count}


# History and versioning endpoints


@app.get("/api/configs/{service_name}/history")
def get_config_history(
    service_name: str,
    environment: str = Query("default", description="Environment name"),
    limit: int = Query(10, description="Maximum versions to return"),
) -> list[dict[str, Any]]:
    """Get configuration history."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return registry_service.get_config_history(service_name, environment, limit)


@app.get("/api/configs/{service_name}/diff")
def diff_configs(
    service_name: str,
    environment: str = Query("default", description="Environment name"),
    old_version: int | None = Query(None, description="Old version (defaults to latest - 1)"),
    new_version: int | None = Query(None, description="New version (defaults to latest)"),
) -> ConfigDiff:
    """Compare two configuration versions."""
    if not registry_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return registry_service.diff_configs(service_name, environment, old_version, new_version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def main():
    """Main entry point."""
    # Load config for port
    config = load_typed_config("config-registry")
    port = config.http_port if hasattr(config, "http_port") else 8000

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_config=create_uvicorn_log_config(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
