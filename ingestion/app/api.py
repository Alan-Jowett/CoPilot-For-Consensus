# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""REST API for ingestion source management."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from copilot_logging import Logger


class SourceConfig(BaseModel):
    """Source configuration model for API."""
    
    name: str = Field(..., description="Unique name for the source")
    source_type: str = Field(..., description="Type of source (rsync, http, imap, local)")
    url: str = Field(..., description="Source URL or connection string")
    port: Optional[int] = Field(None, description="Port number (for IMAP sources)")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    folder: Optional[str] = Field(None, description="Folder path (for IMAP sources)")
    enabled: bool = Field(True, description="Whether the source is enabled for ingestion")
    schedule: Optional[str] = Field(None, description="Cron expression for scheduling (e.g., '0 */6 * * *')")


class SourceStatus(BaseModel):
    """Source status information."""
    
    name: str
    enabled: bool
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_error: Optional[str] = None
    next_run_at: Optional[str] = None
    files_processed: int = 0
    files_skipped: int = 0


class TriggerResponse(BaseModel):
    """Response for manual trigger."""
    
    source_name: str
    status: str
    message: str
    triggered_at: str


def create_api_router(service: Any, logger: Logger) -> APIRouter:
    """Create FastAPI router for ingestion source management.
    
    Args:
        service: IngestionService instance
        logger: Logger instance
        
    Returns:
        APIRouter instance
    """
    router = APIRouter()
    
    @router.get("/health")
    def health():
        """Health check endpoint."""
        stats = service.get_stats()
        
        return {
            "status": "healthy",
            "service": "ingestion",
            "version": getattr(service, "version", "unknown"),
            "sources_configured": stats.get("sources_configured", 0),
            "sources_enabled": stats.get("sources_enabled", 0),
            "last_ingestion_at": stats.get("last_ingestion_at"),
            "total_files_ingested": stats.get("total_files_ingested", 0),
        }
    
    @router.get("/stats")
    def get_stats():
        """Get ingestion service statistics."""
        return service.get_stats()
    
    @router.get("/api/sources", response_model=Dict[str, Any])
    def list_sources(
        enabled_only: bool = Query(False, description="Return only enabled sources"),
    ):
        """List all ingestion sources."""
        try:
            sources = service.list_sources(enabled_only=enabled_only)
            return {
                "sources": sources,
                "count": len(sources),
            }
        except Exception as e:
            logger.error("Error listing sources: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/sources/{source_name}", response_model=Dict[str, Any])
    def get_source(source_name: str):
        """Get a specific source by name."""
        try:
            source = service.get_source(source_name)
            if not source:
                raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
            return source
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting source %s: %s", source_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/sources", response_model=Dict[str, Any], status_code=201)
    def create_source(source: SourceConfig):
        """Create a new ingestion source."""
        try:
            created_source = service.create_source(source.model_dump())
            return {
                "message": f"Source '{source.name}' created successfully",
                "source": created_source,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Error creating source: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/api/sources/{source_name}", response_model=Dict[str, Any])
    def update_source(
        source_name: str,
        source: SourceConfig,
    ):
        """Update an existing source."""
        if source_name != source.name:
            raise HTTPException(
                status_code=400,
                detail="Source name in URL must match name in request body"
            )
        
        try:
            updated_source = service.update_source(source_name, source.model_dump())
            if not updated_source:
                raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
            
            return {
                "message": f"Source '{source_name}' updated successfully",
                "source": updated_source,
            }
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Error updating source %s: %s", source_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/api/sources/{source_name}", response_model=Dict[str, str])
    def delete_source(source_name: str):
        """Delete a source."""
        try:
            success = service.delete_source(source_name)
            if not success:
                raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
            
            return {"message": f"Source '{source_name}' deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error deleting source %s: %s", source_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/sources/{source_name}/trigger", response_model=TriggerResponse)
    def trigger_ingestion(source_name: str):
        """Trigger manual ingestion for a source."""
        try:
            triggered_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            success, message = service.trigger_ingestion(source_name)
            
            if not success:
                raise HTTPException(status_code=400, detail=message)
            
            return TriggerResponse(
                source_name=source_name,
                status="triggered",
                message=message,
                triggered_at=triggered_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error triggering ingestion for %s: %s", source_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/sources/{source_name}/status", response_model=SourceStatus)
    def get_source_status(source_name: str):
        """Get the status of a specific source."""
        try:
            status = service.get_source_status(source_name)
            if not status:
                raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
            
            return SourceStatus(**status)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting status for %s: %s", source_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return router
