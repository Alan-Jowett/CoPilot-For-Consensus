<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Reporting UI (React)

A single page application that replicates the behavior of the Flask-based `reporting-ui` service using React + Vite.

## Features

- Reports list with filters: date range, source, thread, participants/messages counts
- Topic-based semantic search (uses `/api/reports/search`)
- Pagination for non-topic queries
- Report detail with markdown rendering and citations
- Thread summary page linking to full report

## Configuration

- `VITE_REPORTING_API_URL` (optional): Base URL for the Reporting API. Defaults to `http://localhost:8080`.

## Run Locally

```bash
cd reporting-ui-react
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
npm run preview  # serves on port 8083 by default
```

## Docker

Build and run the production image:

```bash
docker build -t reporting-ui-react:local -f Dockerfile .
docker run --rm -p 8083:80 -e VITE_REPORTING_API_URL="http://host.docker.internal:8080" reporting-ui-react:local
```
