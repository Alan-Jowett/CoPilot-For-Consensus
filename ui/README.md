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

## Development

### Run Locally

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

### Testing

The UI uses [Vitest](https://vitest.dev/) and [React Testing Library](https://testing-library.com/react) for testing.

#### Run tests

```bash
# Run all tests once
npm test

# Run tests in watch mode (interactive)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run tests with UI (for debugging)
npm run test:ui
```

#### Test structure

- Tests are colocated with source files using the `.test.ts` or `.test.tsx` extension
- Test utilities and setup files are in `src/test/`
- Tests use `@testing-library/react` for component testing
- API calls are mocked using `vi.fn()` from Vitest

#### Writing tests

Example test structure:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MyComponent } from './MyComponent'

describe('MyComponent', () => {
  beforeEach(() => {
    // Setup code
  })

  it('renders correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const user = userEvent.setup()
    render(<MyComponent />)
    await user.click(screen.getByRole('button'))
    expect(screen.getByText('Clicked')).toBeInTheDocument()
  })
})
```

For mocking API calls, use the utilities in `src/test/testUtils.ts`:

```typescript
import { createMockResponse, createMockFetch } from './test/testUtils'

const fetchMock = vi.fn()
fetchMock.mockResolvedValue(createMockResponse({ data: 'value' }))
global.fetch = fetchMock
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
