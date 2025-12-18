<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Web UI (React)

A single page application intended to be the primary UI for the project. It replaces the legacy Flask-based reporting UI and will expand to include user management, ingestion source management, and browsing emails/threads.

## Features

- Reports list with filters: date range, source, thread, participants/messages counts
- Topic-based semantic search (uses `/api/reports/search`)
- Pagination for non-topic queries
- Report detail with markdown rendering and citations
- Thread summary page linking to full report

## Configuration

- `VITE_REPORTING_API_URL` (optional): Base URL for the Reporting API. Defaults to same-origin (empty string) and relies on the Nginx `/api` proxy in Docker.

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

Build and run the production image:

```bash
docker build -t copilot-ui:local -f Dockerfile .
docker run --rm -p 8084:80 -e VITE_REPORTING_API_URL="http://host.docker.internal:8080" copilot-ui:local
```
