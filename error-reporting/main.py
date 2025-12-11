# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Main error reporting service application."""

import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from app.error_store import ErrorStore, ErrorEvent
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates')
error_store = ErrorStore(max_errors=10000)


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
        "level": "error|warning|critical",
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
        error_id = error_store.add_error(error_event)
        
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
        limit = min(int(request.args.get("limit", 100)), 1000)
        offset = int(request.args.get("offset", 0))
        
        errors = error_store.get_errors(
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
        error = error_store.get_error_by_id(error_id)
        
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
        stats = error_store.get_stats()
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
        errors = error_store.get_errors(
            service=service,
            level=level,
            limit=100
        )
        
        # Get stats
        stats = error_store.get_stats()
        
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
    logger.info("Starting Error Reporting Service on port 8081")
    app.run(host="0.0.0.0", port=8081, debug=False)
