// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { DiscussionsList } from './DiscussionsList'
import { createMockResponse } from '../test/testUtils'

describe('DiscussionsList', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mockSources = ['test-source-a', 'test-source-b']
  const mockThreads = [
    {
      _id: 'thread1',
      subject: 'Test Discussion 1',
      first_message_date: '2025-01-10T00:00:00Z',
      last_message_date: '2025-01-15T00:00:00Z',
      participants: ['alice@example.com', 'bob@example.com'],
      message_count: 10,
      archive_source: 'test-source-a',
      summary_id: 'summary1',
    },
    {
      _id: 'thread2',
      subject: 'Test Discussion 2',
      first_message_date: '2025-01-20T00:00:00Z',
      last_message_date: '2025-01-25T00:00:00Z',
      participants: ['charlie@example.com'],
      message_count: 5,
      archive_source: 'test-source-b',
      summary_id: null,
    },
  ]

  it('renders loading state', async () => {
    fetchMock.mockImplementation(() => new Promise(() => {})) // Never resolves

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    expect(screen.getByText(/Loading threads/i)).toBeInTheDocument()
  })

  it('renders threads table', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: mockThreads, count: 2 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Test Discussion 1')).toBeInTheDocument()
    })

    expect(screen.getByText('Test Discussion 2')).toBeInTheDocument()
    // Source names appear in both dropdown options and table cells
    expect(screen.getAllByText('test-source-a').length).toBeGreaterThan(0)
    expect(screen.getAllByText('test-source-b').length).toBeGreaterThan(0)
  })

  it('renders summary link when summary_id exists', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: mockThreads, count: 2 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Test Discussion 1')).toBeInTheDocument()
    })

    // Check that thread1 has a summary link
    const summaryLinks = screen.getAllByText(/📄 View/)
    expect(summaryLinks.length).toBeGreaterThan(0)
  })

  it('renders dash when no summary_id', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [mockThreads[1]], count: 1 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Test Discussion 2')).toBeInTheDocument()
    })

    // Thread2 has no summary, so we should see a dash
    const cells = screen.getAllByRole('cell')
    const dashCells = cells.filter(cell => cell.textContent === '—')
    expect(dashCells.length).toBeGreaterThan(0)
  })

  it('toggle advanced filters', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByText(/Loading threads/i)).not.toBeInTheDocument()
    })

    // Advanced filters should be hidden initially
    expect(screen.queryByLabelText(/Min Participants/i)).not.toBeInTheDocument()

    // Click toggle button
    const toggleButton = screen.getByText(/Advanced/)
    await userEvent.click(toggleButton)

    // Now advanced filters should be visible
    await waitFor(() => {
      expect(screen.getByLabelText(/Min Participants/i)).toBeInTheDocument()
    })
  })

  it('apply filters calls fetchThreadsList', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByText(/Loading threads/i)).not.toBeInTheDocument()
    })

    // Select a source
    const sourceSelect = screen.getByLabelText(/Source/i)
    await userEvent.selectOptions(sourceSelect, 'test-source-a')

    // Mock the next fetch for when we apply filters
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    // Click apply filters
    const applyButton = screen.getByText(/Apply Filters/i)
    await userEvent.click(applyButton)

    // Wait for the new API call
    await waitFor(() => {
      const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]
      expect(lastCall[0]).toContain('source=test-source-a')
    })
  })

  it('pagination controls work', async () => {
    // Need 20 threads to fill a page so Next button is enabled
    const fullPage = Array.from({ length: 20 }, (_, i) => ({
      _id: `thread${i}`,
      subject: `Discussion ${i}`,
      first_message_date: '2025-01-10T00:00:00Z',
      last_message_date: '2025-01-15T00:00:00Z',
      participants: ['alice@example.com'],
      message_count: 1,
      archive_source: 'test-source-a',
      summary_id: null,
    }))

    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: fullPage, count: 20 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Discussion 0')).toBeInTheDocument()
    })

    // Previous button should be disabled on first page
    const prevButton = screen.getByText(/Previous/)
    expect(prevButton).toBeDisabled()

    // Mock next page fetch (sources + threads)
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    // Click next
    const nextButton = screen.getByText(/Next/)
    await userEvent.click(nextButton)

    await waitFor(() => {
      const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]
      expect(lastCall[0]).toContain('skip=20')
    })
  })

  it('quick date buttons populate fields', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByText(/Loading threads/i)).not.toBeInTheDocument()
    })

    // Click "Last 30 days" button
    const button = screen.getByText(/Last 30 days/)
    await userEvent.click(button)

    // Check that date inputs are populated
    const dateInputs = screen.getAllByDisplayValue(/2025-|2026-/)
    expect(dateInputs.length).toBeGreaterThanOrEqual(2)
  })

  it('source dropdown populated from API', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByText(/Loading threads/i)).not.toBeInTheDocument()
    })

    // Check that dropdown has the sources
    const sourceSelect = screen.getByLabelText(/Source/i)
    expect(sourceSelect).toBeInTheDocument()
    
    const options = screen.getAllByRole('option')
    const sourceTexts = options.map(opt => opt.textContent)
    expect(sourceTexts).toContain('test-source-a')
    expect(sourceTexts).toContain('test-source-b')
  })

  it('displays error message', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: [] }))
    fetchMock.mockRejectedValueOnce(new Error('Network error'))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/Error/i)).toBeInTheDocument()
    })
  })

  it('displays no results message', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/No threads found matching your filters/i)).toBeInTheDocument()
    })
  })

  it('displays page heading and subtitle', async () => {
    fetchMock.mockResolvedValueOnce(createMockResponse({ sources: mockSources }))
    fetchMock.mockResolvedValueOnce(createMockResponse({ threads: [], count: 0 }))

    render(
      <MemoryRouter>
        <DiscussionsList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Discussions')).toBeInTheDocument()
    })

    expect(screen.getByText(/Browse mailing list discussion threads/i)).toBeInTheDocument()
  })
})
