# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main error reporting service application."""

import logging
from datetime import datetime
from flask import Flask, request, render_template
from copilot_config import load_typed_config
from app.error_store import ErrorStore, ErrorEvent
import uuid
from functools import lru_cache

# Valid error levels
VALID_LEVELS = {"error", "warning", "critical", "info"}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

# Lazy-loaded configuration and error store
config = None
error_store = None


@lru_cache(maxsize=1)
def get_config():
    """Load and cache service configuration lazily."""
    return load_typed_config("error-reporting")


def get_error_store() -> ErrorStore:
    """Get or initialize the ErrorStore with configured capacity."""
    global error_store
    if error_store is None:
        error_store = ErrorStore(max_errors=get_config().max_errors)
    return error_store


@app.route("/", methods=["GET"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "error-reporting"}, 200


@app.route("/api/errors", methods=["POST"])
def report_error():
    """
    Report a new error event.
    
    Expected JSON body:
    {
        "service": "service-name",
        "level": "error|warning|critical|info",
        "message": "Error message",
        "error_type": "ValueError",  # optional
        "stack_trace": "...",         # optional
        "context": {...}              # optional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return {"error": "No JSON data provided"}, 400
        
        # Validate required fields
        required_fields = ["service", "level", "message"]
        for field in required_fields:
            if field not in data:
                return {"error": f"Missing required field: {field}"}, 400
        
        # Validate error level
        if data["level"] not in VALID_LEVELS:
            return {
                "error": f"Invalid level. Must be one of: {', '.join(sorted(VALID_LEVELS))}"
            }, 400
        
        # Create error event
        error_event = ErrorEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + 'Z',
            service=data["service"],
            level=data["level"],
            message=data["message"],
            error_type=data.get("error_type"),
            stack_trace=data.get("stack_trace"),
            context=data.get("context")
        )
        
        # Store error
        error_id = get_error_store().add_error(error_event)
        
        logger.info(f"Received error from {data['service']}: {data['message'][:100]}")
        
        return {
            "status": "ok",
            "error_id": error_id
        }, 201
        
    except Exception as e:
        logger.error(f"Failed to process error report: {str(e)}")
        return {"error": "Internal server error"}, 500


@app.route("/api/errors", methods=["GET"])
def get_errors():
    """
    Get errors with optional filtering.
    
    Query parameters:
    - service: Filter by service name
    - level: Filter by error level
    - error_type: Filter by error type
    - limit: Maximum number of errors to return (default: 100, max: 1000)
    - offset: Number of errors to skip (default: 0)
    """
    try:
        service = request.args.get("service")
        level = request.args.get("level")
        error_type = request.args.get("error_type")
        
        # Validate and parse limit parameter
        limit_raw = request.args.get("limit", "100")
        try:
            limit = int(limit_raw)
            if limit < 1 or limit > 1000:
                return {"error": "'limit' must be between 1 and 1000"}, 400
        except (TypeError, ValueError):
            return {"error": "Invalid 'limit' parameter, must be an integer"}, 400
        
        # Validate and parse offset parameter
        offset_raw = request.args.get("offset", "0")
        try:
            offset = int(offset_raw)
            if offset < 0:
                return {"error": "'offset' must be 0 or greater"}, 400
        except (TypeError, ValueError):
            return {"error": "Invalid 'offset' parameter, must be an integer"}, 400
        
        errors = get_error_store().get_errors(
            service=service,
            level=level,
            error_type=error_type,
            limit=limit,
            offset=offset
        )
        
        return {
            "errors": [e.to_dict() for e in errors],
            "count": len(errors),
            "limit": limit,
            "offset": offset
        }, 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve errors: {str(e)}")
        return {"error": "Internal server error"}, 500


@app.route("/api/errors/<error_id>", methods=["GET"])
def get_error(error_id):
    """Get a specific error by ID."""
    try:
        error = get_error_store().get_error_by_id(error_id)
        
        if not error:
            return {"error": "Error not found"}, 404
        
        return error.to_dict(), 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve error: {str(e)}")
        return {"error": "Internal server error"}, 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get error statistics."""
    try:
        stats = get_error_store().get_stats()
        return stats, 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve stats: {str(e)}")
        return {"error": "Internal server error"}, 500


@app.route("/ui", methods=["GET"])
def ui():
    """Web UI for viewing errors."""
    try:
        # Get query parameters
        service = request.args.get("service")
        level = request.args.get("level")
        
        # Get errors
        errors = get_error_store().get_errors(
            service=service,
            level=level,
            limit=100
        )
        
        # Get stats
        stats = get_error_store().get_stats()
        
        return render_template(
            "errors.html",
            errors=errors,
            stats=stats,
            selected_service=service,
            selected_level=level
        )
        
    except Exception as e:
        logger.error(f"Failed to render UI: {str(e)}")
        return f"Error rendering UI: {str(e)}", 500


if __name__ == "__main__":
    port = get_config().http_port
    logger.info(f"Starting Error Reporting Service on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
