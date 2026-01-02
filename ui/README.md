<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Web UI (React)

A single page application intended to be the primary UI for the project. It replaces the legacy Flask-based reporting UI and will expand to include user management, ingestion source management, and browsing emails/threads.

## Features

- Reports list with filters: date range, source, thread, participants/messages counts
- Topic-based semantic search (uses `/reporting/api/reports/search`)
- Pagination for non-topic queries
- Report detail with markdown rendering and citations
- Thread summary page linking to full report

## Configuration

- `VITE_REPORTING_API_URL` (optional): Base URL for the Reporting API. Defaults to same-origin (empty string) and relies on the Nginx `/reporting` proxy in Docker.

## Run Locally

```bash
cd ui
npm install
npm run dev
```

Open the app at http://localhost:5173.

To point at a non-default API base:

```bash
VITE_REPORTING_API_URL=http://localhost:8080 npm run dev
```

## Build & Preview

```bash
npm run build
npm run preview  # serves on port 4173 by default
```

## Docker

The UI is deployed as part of the Docker Compose stack and accessed via the API Gateway:

```bash
# Start all services including the UI
docker compose up -d

# Access the UI via the gateway
open http://localhost:8080/ui/
```

**Note**: All testing should be done via the gateway at `http://localhost:8080/ui/`. The UI container serves static files only; the gateway handles all API routing, authentication, and service proxying.
