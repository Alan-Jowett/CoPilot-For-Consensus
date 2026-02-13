// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchThreadsList, fetchSources, ThreadsQuery, Thread } from '../api'
import { AccessDenied } from '../components/AccessDenied'

function useQueryState() {
  const [sp, setSp] = useSearchParams()
  const q = useMemo<ThreadsQuery>(() => ({
    message_start_date: sp.get('message_start_date') ?? undefined,
    message_end_date: sp.get('message_end_date') ?? undefined,
    source: sp.get('source') ?? undefined,
    min_participants: sp.get('min_participants') ?? undefined,
    max_participants: sp.get('max_participants') ?? undefined,
    min_messages: sp.get('min_messages') ?? undefined,
    max_messages: sp.get('max_messages') ?? undefined,
    limit: Number(sp.get('limit') ?? 20),
    skip: Number(sp.get('skip') ?? 0),
    sort_by: sp.get('sort_by') ?? 'first_message_date',
    sort_order: sp.get('sort_order') ?? 'desc',
  }), [sp])

  const update = (patch: Partial<ThreadsQuery>) => {
    const next = new URLSearchParams(sp)
    Object.entries(patch).forEach(([k, v]) => {
      if (v === undefined || v === null || `${v}`.length === 0) next.delete(k)
      else next.set(k, String(v))
    })
    if (!('skip' in patch)) next.set('skip', '0')
    setSp(next, { replace: false })
  }

  const clearAll = () => {
    setSp(new URLSearchParams({}), { replace: false })
  }

  const remove = (key: string) => {
    const next = new URLSearchParams(sp)
    next.delete(key)
    next.set('skip', '0')
    setSp(next, { replace: false })
  }

  return { q, update, clearAll, remove }
}

export function DiscussionsList() {
  const { q, update, clearAll, remove } = useQueryState()
  const [availableSources, setAvailableSources] = useState<string[]>([])
  const [data, setData] = useState<{ threads: Thread[]; count: number }>({ threads: [], count: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accessDenied, setAccessDenied] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setAccessDenied(null)
    ;(async () => {
      try {
        const [sources, result] = await Promise.all([
          fetchSources(),
          fetchThreadsList(q),
        ])
        if (cancelled) return
        setAvailableSources(sources)
        setData(result)
      } catch (e: unknown) {
        if (cancelled) return
        let message = 'Failed to load threads'
        if (e instanceof Error && e.message) {
          // Check if this is an ACCESS_DENIED error
          if (e.message.startsWith('ACCESS_DENIED:')) {
            setAccessDenied(e.message.replace('ACCESS_DENIED: ', '') ?? '')
            return
          }
          message = e.message
        } else if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') {
          message = (e as { message: string }).message
        }
        setError(message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [q])

  const [form, setForm] = useState({
    message_start_date: q.message_start_date ?? '',
    message_end_date: q.message_end_date ?? '',
    source: q.source ?? '',
    min_participants: q.min_participants ?? '',
    max_participants: q.max_participants ?? '',
    min_messages: q.min_messages ?? '',
    max_messages: q.max_messages ?? '',
    limit: String(q.limit ?? 20),
  })

  useEffect(() => {
    setForm(f => ({
      ...f,
      message_start_date: q.message_start_date ?? '',
      message_end_date: q.message_end_date ?? '',
      source: q.source ?? '',
      min_participants: q.min_participants ?? '',
      max_participants: q.max_participants ?? '',
      min_messages: q.min_messages ?? '',
      max_messages: q.max_messages ?? '',
      limit: String(q.limit ?? 20),
    }))
  }, [q])

  function applyFilters(e: React.FormEvent) {
    e.preventDefault()
    update({
      message_start_date: form.message_start_date || undefined,
      message_end_date: form.message_end_date || undefined,
      source: form.source || undefined,
      min_participants: form.min_participants || undefined,
      max_participants: form.max_participants || undefined,
      min_messages: form.min_messages || undefined,
      max_messages: form.max_messages || undefined,
      limit: Number(form.limit || 20),
    })
  }

  function setDateRange(days: number) {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - days)
    setForm(f => ({
      ...f,
      message_start_date: start.toISOString().split('T')[0],
      message_end_date: end.toISOString().split('T')[0],
    }))
  }

  function setCurrentMonth() {
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth(), 1)
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    setForm(f => ({
      ...f,
      message_start_date: start.toISOString().split('T')[0],
      message_end_date: end.toISOString().split('T')[0],
    }))
  }

  function toggleSort() {
    const newOrder = q.sort_order === 'desc' ? 'asc' : 'desc'
    update({ sort_order: newOrder })
  }

  const hasFilters = !!(
    q.message_start_date ||
    q.message_end_date ||
    q.source ||
    q.min_participants ||
    q.max_participants ||
    q.min_messages ||
    q.max_messages
  )

  // Calculate active filter badges
  const activeFilterBadges = []
  if (q.message_start_date) activeFilterBadges.push({ key: 'message_start_date', label: `From: ${q.message_start_date}` })
  if (q.message_end_date) activeFilterBadges.push({ key: 'message_end_date', label: `To: ${q.message_end_date}` })
  if (q.source) activeFilterBadges.push({ key: 'source', label: `Source: ${q.source}` })
  if (q.min_participants) activeFilterBadges.push({ key: 'min_participants', label: `Min participants: ${q.min_participants}` })
  if (q.max_participants) activeFilterBadges.push({ key: 'max_participants', label: `Max participants: ${q.max_participants}` })
  if (q.min_messages) activeFilterBadges.push({ key: 'min_messages', label: `Min messages: ${q.min_messages}` })
  if (q.max_messages) activeFilterBadges.push({ key: 'max_messages', label: `Max messages: ${q.max_messages}` })

  if (accessDenied) {
    return <AccessDenied message={accessDenied} />
  }

  return (
    <div>
      <h1>Discussions</h1>
      <p className="subtitle">Browse mailing list discussion threads</p>

      {/* Filter Form */}
      <form onSubmit={applyFilters} className="filter-form">
        <div className="filter-section">
          <h3>Filters</h3>
          <button
            type="button"
            className="toggle-advanced"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? '▼ Simple' : '▶ Advanced'}
          </button>
        </div>

        {/* Simple Filters */}
        <div className="filter-row">
          <div className="filter-group">
            <label>Date Range:</label>
            <div className="date-inputs">
              <input
                type="date"
                value={form.message_start_date}
                onChange={e => setForm({ ...form, message_start_date: e.target.value })}
                placeholder="Start date"
              />
              <span> to </span>
              <input
                type="date"
                value={form.message_end_date}
                onChange={e => setForm({ ...form, message_end_date: e.target.value })}
                placeholder="End date"
              />
            </div>
            <div className="quick-date-buttons">
              <button type="button" onClick={() => setDateRange(7)}>Last 7 days</button>
              <button type="button" onClick={() => setDateRange(30)}>Last 30 days</button>
              <button type="button" onClick={() => setDateRange(90)}>Last 90 days</button>
              <button type="button" onClick={setCurrentMonth}>Current month</button>
            </div>
          </div>

          <div className="filter-group">
            <label>Source:</label>
            <select
              value={form.source}
              onChange={e => setForm({ ...form, source: e.target.value })}
            >
              <option value="">All sources</option>
              {availableSources.map(src => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Advanced Filters */}
        {showAdvanced && (
          <div className="filter-row advanced-filters">
            <div className="filter-group">
              <label>Participants:</label>
              <div className="range-inputs">
                <input
                  type="number"
                  min="0"
                  value={form.min_participants}
                  onChange={e => setForm({ ...form, min_participants: e.target.value })}
                  placeholder="Min"
                />
                <span> to </span>
                <input
                  type="number"
                  min="0"
                  value={form.max_participants}
                  onChange={e => setForm({ ...form, max_participants: e.target.value })}
                  placeholder="Max"
                />
              </div>
            </div>

            <div className="filter-group">
              <label>Messages:</label>
              <div className="range-inputs">
                <input
                  type="number"
                  min="0"
                  value={form.min_messages}
                  onChange={e => setForm({ ...form, min_messages: e.target.value })}
                  placeholder="Min"
                />
                <span> to </span>
                <input
                  type="number"
                  min="0"
                  value={form.max_messages}
                  onChange={e => setForm({ ...form, max_messages: e.target.value })}
                  placeholder="Max"
                />
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="filter-actions">
          <button type="submit" className="btn-primary">Apply Filters</button>
          {hasFilters && (
            <button type="button" onClick={clearAll} className="btn-secondary">
              Clear All
            </button>
          )}
        </div>
      </form>

      {/* Active Filter Badges */}
      {activeFilterBadges.length > 0 && (
        <div className="active-filters">
          <span className="filter-label">Active filters:</span>
          {activeFilterBadges.map(badge => (
            <span key={badge.key} className="filter-badge">
              {badge.label}
              <button
                type="button"
                className="remove-filter"
                onClick={() => remove(badge.key)}
                title="Remove filter"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Loading/Error States */}
      {loading && <p className="loading">Loading threads...</p>}
      {error && <p className="error">Error: {error}</p>}

      {/* Threads Table */}
      {!loading && !error && (
        <>
          <div className="results-header">
            <p className="result-count">
              Showing {data.threads.length} of {data.count} threads
              {q.skip > 0 && ` (skipping first ${q.skip})`}
            </p>
            <div className="sort-controls">
              <label>Sort by thread start: </label>
              <button
                type="button"
                onClick={toggleSort}
                className="sort-toggle"
                title={`Currently: ${q.sort_order === 'desc' ? 'Newest first' : 'Oldest first'}`}
              >
                {q.sort_order === 'desc' ? '↓ Newest first' : '↑ Oldest first'}
              </button>
            </div>
          </div>

          <table className="threads-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Source</th>
                <th>Date Range</th>
                <th>Participants</th>
                <th>Messages</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {data.threads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="no-results">
                    No threads found matching your filters
                  </td>
                </tr>
              ) : (
                data.threads.map(thread => {
                  const firstDate = thread.first_message_date
                    ? new Date(thread.first_message_date).toLocaleDateString()
                    : '—'
                  const lastDate = thread.last_message_date
                    ? new Date(thread.last_message_date).toLocaleDateString()
                    : '—'
                  const dateRange = firstDate === lastDate ? firstDate : `${firstDate} → ${lastDate}`

                  return (
                    <tr key={thread._id}>
                      <td>
                        <Link to={`/threads/${thread._id}/messages`}>
                          {thread.subject || '(no subject)'}
                        </Link>
                      </td>
                      <td>{thread.archive_source || '—'}</td>
                      <td>{dateRange}</td>
                      <td>{thread.participants?.length ?? 0}</td>
                      <td>{thread.message_count ?? 0}</td>
                      <td>
                        {thread.summary_id ? (
                          <Link to={`/reports/${thread.summary_id}`}>📄 View</Link>
                        ) : (
                          <span>—</span>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>

          {/* Pagination */}
          <div className="pagination">
            <button
              onClick={() => update({ skip: Math.max(0, q.skip - q.limit) })}
              disabled={q.skip === 0}
              className="btn-secondary"
            >
              ← Previous
            </button>
            <span className="pagination-info">
              Page {Math.floor(q.skip / q.limit) + 1}
            </span>
            <button
              onClick={() => update({ skip: q.skip + q.limit })}
              disabled={data.threads.length < q.limit}
              className="btn-secondary"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
