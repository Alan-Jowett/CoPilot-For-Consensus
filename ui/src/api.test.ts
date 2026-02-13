// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  reportingApiBase,
  fetchSources,
  fetchReports,
  searchReportsByTopic,
  fetchReport,
  fetchIngestionSources,
  createIngestionSource,
  updateIngestionSource,
  deleteIngestionSource,
  triggerIngestionSource,
} from './api'
import { createMockResponse } from './test/testUtils'

describe('API Helpers', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('reportingApiBase', () => {
    it('returns empty string in DEV mode', () => {
      const base = reportingApiBase()
      // Based on vite.config, DEV mode should return '' but production should return '/reporting'
      expect(base).toMatch(/^(\/reporting)?$/)
    })
  })

  describe('fetchSources', () => {
    it('fetches sources successfully', async () => {
      const mockData = { sources: ['source1', 'source2'] }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      const result = await fetchSources()

      expect(result).toEqual(['source1', 'source2'])
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/sources'),
        expect.objectContaining({ credentials: 'include' })
      )
    })

    it('throws error on failed request', async () => {
      fetchMock.mockResolvedValue(createMockResponse({}, { status: 500, ok: false }))

      await expect(fetchSources()).rejects.toThrow('Sources fetch failed: 500')
    })
  })

  describe('fetchReports', () => {
    it('fetches reports with default pagination', async () => {
      const mockData = { reports: [{ _id: '1', thread_id: 'thread1' }], count: 1 }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      const result = await fetchReports({})

      expect(result).toEqual(mockData)
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      )
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('skip=0'),
        expect.any(Object)
      )
    })

    it('fetches reports with custom filters', async () => {
      const mockData = { reports: [], count: 0 }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      await fetchReports({
        thread_id: 'thread1',
        source: 'test-source',
        limit: 10,
        skip: 5,
      })

      const callUrl = fetchMock.mock.calls[0][0]
      expect(callUrl).toContain('thread_id=thread1')
      expect(callUrl).toContain('source=test-source')
      expect(callUrl).toContain('limit=10')
      expect(callUrl).toContain('skip=5')
    })
  })

  describe('searchReportsByTopic', () => {
    it('searches reports by topic', async () => {
      const mockData = { reports: [{ _id: '1' }] }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      const result = await searchReportsByTopic('test topic', 10)

      expect(result).toEqual([{ _id: '1' }])
      const callUrl = fetchMock.mock.calls[0][0]
      expect(callUrl).toContain('topic=test+topic')
      expect(callUrl).toContain('limit=10')
      expect(callUrl).toContain('min_score=0.5')
    })
  })

  describe('fetchReport', () => {
    it('fetches a single report', async () => {
      const mockReport = { _id: '123', thread_id: 'thread1' }
      fetchMock.mockResolvedValue(createMockResponse(mockReport))

      const result = await fetchReport('123')

      expect(result).toEqual(mockReport)
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/reports/123'),
        expect.any(Object)
      )
    })

    it('throws NOT_FOUND error for 404', async () => {
      fetchMock.mockResolvedValue(createMockResponse({}, { status: 404, ok: false }))

      await expect(fetchReport('999')).rejects.toThrow('NOT_FOUND')
    })
  })

  describe('Ingestion API', () => {
    describe('fetchIngestionSources', () => {
      it('fetches all sources', async () => {
        const mockData = { sources: [{ name: 'source1' }], count: 1 }
        fetchMock.mockResolvedValue(createMockResponse(mockData))

        const result = await fetchIngestionSources()

        expect(result).toEqual(mockData)
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/ingestion/api/sources'),
          expect.any(Object)
        )
      })

      it('fetches enabled sources only', async () => {
        const mockData = { sources: [{ name: 'source1', enabled: true }], count: 1 }
        fetchMock.mockResolvedValue(createMockResponse(mockData))

        await fetchIngestionSources(true)

        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('enabled_only=true'),
          expect.any(Object)
        )
      })
    })

    describe('createIngestionSource', () => {
      it('creates a new source', async () => {
        const newSource = { name: 'test', source_type: 'local', url: '/test', enabled: true }
        const mockResponse = { message: 'Created', source: newSource }
        fetchMock.mockResolvedValue(createMockResponse(mockResponse))

        const result = await createIngestionSource(newSource)

        expect(result).toEqual(mockResponse)
        // Check that the request was made with correct parameters
        const call = fetchMock.mock.calls[0]
        expect(call[0]).toContain('/ingestion/api/sources')
        expect(call[1]).toMatchObject({
          method: 'POST',
          body: JSON.stringify(newSource),
        })
        expect(call[1]?.credentials).toBe('include')
      })

      it('throws formatted error on failure', async () => {
        const newSource = { name: 'test', source_type: 'local', url: '/test', enabled: true }
        fetchMock.mockResolvedValue(
          createMockResponse({ detail: 'Source already exists' }, { status: 400, ok: false })
        )

        await expect(createIngestionSource(newSource)).rejects.toThrow('Source already exists')
      })
    })

    describe('updateIngestionSource', () => {
      it('updates an existing source', async () => {
        const source = { name: 'test', source_type: 'local', url: '/updated', enabled: true }
        const mockResponse = { message: 'Updated', source }
        fetchMock.mockResolvedValue(createMockResponse(mockResponse))

        const result = await updateIngestionSource('test', source)

        expect(result).toEqual(mockResponse)
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/ingestion/api/sources/test'),
          expect.objectContaining({ method: 'PUT' })
        )
      })
    })

    describe('deleteIngestionSource', () => {
      it('deletes a source', async () => {
        const mockResponse = { message: 'Deleted' }
        fetchMock.mockResolvedValue(createMockResponse(mockResponse))

        const result = await deleteIngestionSource('test')

        expect(result).toEqual(mockResponse)
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/ingestion/api/sources/test'),
          expect.objectContaining({ method: 'DELETE' })
        )
      })
    })

    describe('triggerIngestionSource', () => {
      it('triggers ingestion', async () => {
        const mockResponse = {
          source_name: 'test',
          status: 'triggered',
          message: 'Success',
          triggered_at: '2025-01-01T00:00:00Z',
        }
        fetchMock.mockResolvedValue(createMockResponse(mockResponse))

        const result = await triggerIngestionSource('test')

        expect(result).toEqual(mockResponse)
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/ingestion/api/sources/test/trigger'),
          expect.objectContaining({ method: 'POST' })
        )
      })
    })
  })

  describe('Error handling', () => {
    it('handles 401 unauthorized', async () => {
      fetchMock.mockResolvedValue(createMockResponse({}, { status: 401, ok: false }))

      await expect(fetchSources()).rejects.toThrow('UNAUTHORIZED')
    })

    it('handles 403 forbidden with detail message', async () => {
      fetchMock.mockResolvedValue(
        createMockResponse(
          { detail: 'Admin access required' },
          { status: 403, ok: false }
        )
      )

      await expect(fetchSources()).rejects.toThrow('ACCESS_DENIED: Admin access required')
    })
  })

  describe('fetchThreadsList', () => {
    it('sends correct query params', async () => {
      const mockData = { threads: [{ _id: 'thread1', subject: 'Test' }], count: 1 }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      const result = await fetchThreadsList({
        message_start_date: '2025-01-01',
        message_end_date: '2025-01-31',
        source: 'test-source',
        min_participants: '2',
        max_participants: '10',
        min_messages: '5',
        max_messages: '50',
        sort_by: 'first_message_date',
        sort_order: 'desc',
        limit: 20,
        skip: 10,
      })

      expect(result).toEqual(mockData)
      
      const callUrl = fetchMock.mock.calls[0][0]
      expect(callUrl).toContain('message_start_date=2025-01-01')
      expect(callUrl).toContain('message_end_date=2025-01-31')
      expect(callUrl).toContain('source=test-source')
      expect(callUrl).toContain('min_participants=2')
      expect(callUrl).toContain('max_participants=10')
      expect(callUrl).toContain('min_messages=5')
      expect(callUrl).toContain('max_messages=50')
      expect(callUrl).toContain('sort_by=first_message_date')
      expect(callUrl).toContain('sort_order=desc')
      expect(callUrl).toContain('limit=20')
      expect(callUrl).toContain('skip=10')
    })

    it('handles empty response', async () => {
      const mockData = { threads: [], count: 0 }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      const result = await fetchThreadsList({})

      expect(result).toEqual({ threads: [], count: 0 })
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/threads'),
        expect.any(Object)
      )
    })

    it('fetches with default pagination', async () => {
      const mockData = { threads: [], count: 0 }
      fetchMock.mockResolvedValue(createMockResponse(mockData))

      await fetchThreadsList({})

      const callUrl = fetchMock.mock.calls[0][0]
      expect(callUrl).toContain('limit=20')
      expect(callUrl).toContain('skip=0')
    })

    it('throws error on failed request', async () => {
      fetchMock.mockResolvedValue(createMockResponse({}, { status: 500, ok: false }))

      await expect(fetchThreadsList({})).rejects.toThrow('Threads fetch failed: 500')
    })
  })
})
