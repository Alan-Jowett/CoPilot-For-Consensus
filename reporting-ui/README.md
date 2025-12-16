<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Reporting UI Service

## Overview

The Reporting UI Service provides a human-accessible web interface for viewing reports (summaries + citations) produced by the reporting service. It consumes the existing reporting API endpoints and presents them in an easy-to-use web interface.

## Purpose

- Allow operators and stakeholders to quickly verify that ingestion → summarization → reporting is working without hitting raw APIs
- Provide a simple UI for browsing and inspecting reports
- Display summary markdown rendered in a readable format
- Show citations with source IDs in a structured table
- Enable copy-to-clipboard functionality for IDs

## Technology Stack

- **Language:** Python 3.10+
- **Framework:** Flask (Web UI)
- **Dependencies:** requests (for API calls), marked.js (for markdown rendering)

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `HTTP_PORT` | Integer | No | `8083` | HTTP server port |
| `REPORTING_API_URL` | String | Yes | `http://reporting:8080` | Base URL for reporting API |

## Features

### Pages

1. **Reports List** (`/reports`)
   - View all reports with pagination
   - Filter by thread ID
   - Configurable results per page
   - Copy-to-clipboard for IDs

2. **Report Detail** (`/reports/<report_id>`)
   - Full summary with markdown rendering
   - Citations table with chunk IDs and message IDs
   - Performance metrics (tokens, latency, model info)
   - Copy-to-clipboard for all IDs

3. **Thread Summary** (`/threads/<thread_id>`)
   - Latest summary for a specific thread
   - Quick access to thread-specific reports

## API Consumption

The UI consumes the following reporting service endpoints:
- `GET /api/reports` - List reports with filters
- `GET /api/reports/{id}` - Get specific report
- `GET /api/threads/{thread_id}/summary` - Get latest thread summary

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export REPORTING_API_URL=http://localhost:8080
export HTTP_PORT=8083
python main.py

# Docker
docker build -t copilot-reporting-ui .
docker run -d \
  -e REPORTING_API_URL=http://reporting:8080 \
  -p 8083:8083 \
  copilot-reporting-ui
```

## Security Notes

This service has **NO authentication or authorization** in the initial version. It is intended for local development and internal use only. Do NOT expose this service to untrusted networks or in production environments without adding proper authentication.

## Non-Goals (for initial version)

- Authentication/authorization (can be added later if needed)
- Direct database access (only uses reporting API)
- Editing reports
- Vector search interface (falls back to simple filtering)

## Future Enhancements

- [ ] Authentication and authorization
- [ ] Search functionality (when vector search is enabled)
- [ ] Date range filtering
- [ ] Draft flag filtering
- [ ] Export functionality (PDF, JSON)
- [ ] Responsive mobile design improvements
