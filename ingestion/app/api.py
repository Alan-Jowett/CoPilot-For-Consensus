# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""REST API for ingestion source management."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
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


class UploadResponse(BaseModel):
    """Response for file upload."""

    filename: str
    server_path: str
    size_bytes: int
    uploaded_at: str
    suggested_source_type: str = "local"


# Maximum upload size in bytes (100 MB)
MAX_UPLOAD_SIZE = 100 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".mbox", ".zip", ".tar", ".tar.gz", ".tgz"}


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other security issues.

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized filename safe for filesystem operations
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Remove any non-alphanumeric characters except dots, hyphens, and underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Ensure filename is not empty and doesn't start with a dot
    if not filename or filename.startswith('.'):
        filename = f"upload_{filename}"

    # Limit length, preserving compound extensions like .tar.gz
    if len(filename) > 255:
        name, ext = _split_extension(filename)
        filename = name[:255 - len(ext)] + ext

    return filename


def _split_extension(filename: str) -> tuple:
    """Split filename into name and extension, handling compound extensions.

    Args:
        filename: Filename to split

    Returns:
        Tuple of (name, extension) where extension includes compound extensions
    """
    lower_filename = filename.lower()

    # Check for compound extensions in priority order (longest first)
    compound_exts = ['.tar.gz', '.tgz']
    for ext in compound_exts:
        if lower_filename.endswith(ext):
            return (filename[:-len(ext)], ext)

    # Fall back to standard split for simple extensions
    return os.path.splitext(filename)


def _validate_file_extension(filename: str) -> bool:
    """Check if file has an allowed extension.

    Args:
        filename: Filename to check

    Returns:
        True if extension is allowed
    """
    # Use the same extension splitting logic for consistency
    _, ext = _split_extension(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


def create_api_router(service: Any, logger: Logger) -> APIRouter:
    """Create FastAPI router for ingestion source management.

    Args:
        service: IngestionService instance
        logger: Logger instance

    Returns:
        APIRouter instance
    """
    router = APIRouter()

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

    @router.post("/api/uploads", response_model=UploadResponse, status_code=201)
    async def upload_file(file: UploadFile = File(...)):
        """Upload a mailbox file for ingestion.

        Accepts .mbox, .zip, .tar, .tar.gz, .tgz files up to 100MB.
        Returns metadata including the server path to use when creating a source.
        """
        try:
            logger.debug(
                "Upload request received",
                filename=file.filename,
                content_type=file.content_type,
                file_size_header=file.size,
            )

            # Validate presence of filename
            if not file.filename:
                logger.warning("Upload rejected: no filename provided")
                raise HTTPException(status_code=400, detail="Filename is required")

            # Sanitize filename first to ensure validation and storage use the same name
            safe_filename = _sanitize_filename(file.filename)
            logger.debug("Filename sanitized", original=file.filename, sanitized=safe_filename)

            # Validate file extension on the sanitized filename
            if not _validate_file_extension(safe_filename):
                logger.warning(
                    "Upload rejected: invalid file extension",
                    filename=safe_filename,
                    allowed_extensions=list(ALLOWED_EXTENSIONS),
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
                )

            # Create uploads directory in storage path
            uploads_dir = Path(service.config.storage_path) / "uploads"
            logger.debug("Creating uploads directory", uploads_dir=str(uploads_dir))
            uploads_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename if file already exists
            file_path = uploads_dir / safe_filename
            if file_path.exists():
                logger.debug("File already exists, generating unique name", original_path=str(file_path))
                name, ext = _split_extension(safe_filename)
                counter = 1
                while file_path.exists():
                    file_path = uploads_dir / f"{name}_{counter}{ext}"
                    counter += 1
                logger.debug("Unique filename generated", final_path=str(file_path))

            # Read and validate file size
            logger.debug("Reading file content")
            content = await file.read()
            file_size = len(content)
            logger.debug("File content read", file_size=file_size)

            if file_size > MAX_UPLOAD_SIZE:
                logger.warning(
                    "Upload rejected: file too large",
                    file_size=file_size,
                    max_size=MAX_UPLOAD_SIZE,
                )
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE / (1024 * 1024):.0f}MB"
                )

            if file_size == 0:
                logger.warning("Upload rejected: empty file")
                raise HTTPException(status_code=400, detail="File is empty")

            # Write file to disk
            logger.debug("Writing file to disk", path=str(file_path))
            try:
                with open(file_path, "wb") as f:
                    f.write(content)
                logger.debug("File written successfully", path=str(file_path))
            except IOError as e:
                logger.error(
                    "Failed to write file to disk",
                    path=str(file_path),
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")

            uploaded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            logger.info(
                "File uploaded successfully",
                filename=file_path.name,
                size_bytes=file_size,
                path=str(file_path),
                uploaded_at=uploaded_at,
            )

            return UploadResponse(
                filename=file_path.name,
                server_path=str(file_path),
                size_bytes=file_size,
                uploaded_at=uploaded_at,
                suggested_source_type="local",
            )
        except HTTPException as http_exc:
            logger.debug("HTTPException raised in upload_file", status_code=http_exc.status_code)
            raise
        except Exception as e:
            logger.error(
                "Error uploading file",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return router
