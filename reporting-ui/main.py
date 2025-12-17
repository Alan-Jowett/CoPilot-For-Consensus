# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Reporting UI Service: Web interface for viewing reports and summaries."""

from functools import lru_cache

from flask import Flask, request, render_template
import requests

from copilot_config import load_typed_config
from copilot_logging import create_logger

logger = create_logger(name=__name__)

app = Flask(__name__, template_folder='templates')


@lru_cache(maxsize=1)
def get_config():
    """Load and cache service configuration lazily."""
    return load_typed_config("reporting-ui")


def get_reporting_api_url():
    """Get the reporting API base URL from config."""
    cfg = get_config()
    return cfg.reporting_api_url


@app.route("/")
def root():
    """Root endpoint redirects to reports list."""
    return reports_list()


@app.route("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "reporting-ui"}, 200


@app.route("/reports")
def reports_list():
    """Reports list page with filters."""
    try:
        # Get query parameters
        thread_id = request.args.get("thread_id")
        topic = request.args.get("topic")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        source = request.args.get("source")
        min_participants = request.args.get("min_participants")
        max_participants = request.args.get("max_participants")
        min_messages = request.args.get("min_messages")
        max_messages = request.args.get("max_messages")
        limit = int(request.args.get("limit", 20))
        skip = int(request.args.get("skip", 0))
        
        # Build API request
        api_url = get_reporting_api_url()
        
        # If topic search is requested, use the search endpoint
        if topic and topic.strip():
            params = {
                "topic": topic,
                "limit": limit,
                "min_score": 0.5,
            }
            response = requests.get(f"{api_url}/api/reports/search", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            reports = data.get("reports", [])
            
            # Get available sources for filter dropdown
            sources_response = requests.get(f"{api_url}/api/sources", timeout=10)
            sources_response.raise_for_status()
            available_sources = sources_response.json().get("sources", [])
            
            return render_template(
                "reports_list.html",
                reports=reports,
                count=len(reports),
                limit=limit,
                skip=skip,
                thread_id=thread_id or "",
                topic=topic,
                start_date=start_date or "",
                end_date=end_date or "",
                source=source or "",
                min_participants=min_participants or "",
                max_participants=max_participants or "",
                min_messages=min_messages or "",
                max_messages=max_messages or "",
                available_sources=available_sources,
                is_topic_search=True,
            )
        
        # Otherwise use the regular reports endpoint with filters
        params = {"limit": limit, "skip": skip}
        if thread_id:
            params["thread_id"] = thread_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if source:
            params["source"] = source
        if min_participants:
            params["min_participants"] = min_participants
        if max_participants:
            params["max_participants"] = max_participants
        if min_messages:
            params["min_messages"] = min_messages
        if max_messages:
            params["max_messages"] = max_messages
        
        # Fetch reports from API
        response = requests.get(f"{api_url}/api/reports", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Get available sources for filter dropdown
        sources_response = requests.get(f"{api_url}/api/sources", timeout=10)
        sources_response.raise_for_status()
        available_sources = sources_response.json().get("sources", [])
        
        return render_template(
            "reports_list.html",
            reports=data.get("reports", []),
            count=data.get("count", 0),
            limit=limit,
            skip=skip,
            thread_id=thread_id or "",
            topic=topic or "",
            start_date=start_date or "",
            end_date=end_date or "",
            source=source or "",
            min_participants=min_participants or "",
            max_participants=max_participants or "",
            min_messages=min_messages or "",
            max_messages=max_messages or "",
            available_sources=available_sources,
            is_topic_search=False,
        )
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch reports from API: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Failed to connect to reporting API: {str(e)}"
        ), 503
    except Exception as e:
        logger.error(f"Error rendering reports list: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Internal error: {str(e)}"
        ), 500


@app.route("/reports/<report_id>")
def report_detail(report_id):
    """Report detail page showing full summary and citations."""
    try:
        # Fetch report from API
        api_url = get_reporting_api_url()
        response = requests.get(f"{api_url}/api/reports/{report_id}", timeout=10)
        
        if response.status_code == 404:
            return render_template(
                "error.html",
                error_message=f"Report {report_id} not found"
            ), 404
        
        response.raise_for_status()
        report = response.json()
        
        return render_template(
            "report_detail.html",
            report=report,
        )
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch report {report_id} from API: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Failed to connect to reporting API: {str(e)}"
        ), 503
    except Exception as e:
        logger.error(f"Error rendering report detail: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Internal error: {str(e)}"
        ), 500


@app.route("/threads/<thread_id>")
def thread_summary(thread_id):
    """Thread summary page showing latest summary for a thread."""
    try:
        # Fetch thread summary from API
        api_url = get_reporting_api_url()
        response = requests.get(f"{api_url}/api/threads/{thread_id}/summary", timeout=10)
        
        if response.status_code == 404:
            return render_template(
                "error.html",
                error_message=f"No summary found for thread {thread_id}"
            ), 404
        
        response.raise_for_status()
        summary = response.json()
        
        return render_template(
            "thread_summary.html",
            thread_id=thread_id,
            summary=summary,
        )
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch thread {thread_id} summary from API: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Failed to connect to reporting API: {str(e)}"
        ), 503
    except Exception as e:
        logger.error(f"Error rendering thread summary: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_message=f"Internal error: {str(e)}"
        ), 500


if __name__ == "__main__":
    port = get_config().http_port
    logger.info(f"Starting Reporting UI Service on port {port}")
    logger.info(f"Reporting API URL: {get_reporting_api_url()}")
    app.run(host="0.0.0.0", port=port, debug=False)
