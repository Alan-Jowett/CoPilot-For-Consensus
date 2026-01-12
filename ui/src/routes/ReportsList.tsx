// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchReports, fetchSources, ReportsQuery, searchReportsByTopic, Report } from '../api'
import { AccessDenied } from '../components/AccessDenied'

function useQueryState() {
  const [sp, setSp] = useSearchParams()
  const q = useMemo<ReportsQuery>(() => ({
    thread_id: sp.get('thread_id') ?? undefined,
    topic: sp.get('topic') ?? undefined,
    message_start_date: sp.get('message_start_date') ?? undefined,
    message_end_date: sp.get('message_end_date') ?? undefined,
    source: sp.get('source') ?? undefined,
    min_participants: sp.get('min_participants') ?? undefined,
    max_participants: sp.get('max_participants') ?? undefined,
    min_messages: sp.get('min_messages') ?? undefined,
    max_messages: sp.get('max_messages') ?? undefined,
    limit: Number(sp.get('limit') ?? 20),
    skip: Number(sp.get('skip') ?? 0),
  }), [sp])

  const update = (patch: Partial<ReportsQuery>) => {
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

export function ReportsList() {
  const { q, update, clearAll, remove } = useQueryState()
  const [availableSources, setAvailableSources] = useState<string[]>([])
  const [data, setData] = useState<{ reports: Report[]; count: number }>({ reports: [], count: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accessDenied, setAccessDenied] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc') // Default: newest first

  const isTopicSearch = !!(q.topic && q.topic.trim())

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setAccessDenied(null)
    ;(async () => {
      try {
        const [sources, result] = await Promise.all([
          fetchSources(),
          (async () => {
            if (isTopicSearch) {
              const reports = await searchReportsByTopic(q.topic!, q.limit)
              return { reports, count: reports.length }
            }
            return await fetchReports(q)
          })(),
        ])
        if (cancelled) return
        setAvailableSources(sources)
        
        // Sort reports by thread start date (first_message_date)
        const sortedReports = [...result.reports].sort((a, b) => {
          const dateA = a.thread_metadata?.first_message_date
          const dateB = b.thread_metadata?.first_message_date
          
          // Handle missing dates - put them at the end
          if (!dateA && !dateB) return 0
          if (!dateA) return 1
          if (!dateB) return -1
          
          // Compare dates
          const comparison = dateA.localeCompare(dateB)
          return sortOrder === 'desc' ? -comparison : comparison
        })
        
        setData({ ...result, reports: sortedReports })
      } catch (e: unknown) {
        if (cancelled) return
        let message = 'Failed to load reports'
        if (e instanceof Error && e?.message) {
          // Check if this is an ACCESS_DENIED error
          if (e?.message?.startsWith('ACCESS_DENIED:')) {
            setAccessDenied(e?.message?.replace('ACCESS_DENIED: ', '') ?? '')
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
  }, [q.topic, q.thread_id, q.message_start_date, q.message_end_date, q.source, q.min_participants, q.max_participants, q.min_messages, q.max_messages, q.limit, q.skip, sortOrder])

  const [form, setForm] = useState({
    topic: q.topic ?? '',
    message_start_date: q.message_start_date ?? '',
    message_end_date: q.message_end_date ?? '',
    source: q.source ?? '',
    thread_id: q.thread_id ?? '',
    min_participants: q.min_participants ?? '',
    max_participants: q.max_participants ?? '',
    min_messages: q.min_messages ?? '',
    max_messages: q.max_messages ?? '',
    limit: String(q.limit ?? 20),
  })

  useEffect(() => {
    setForm(f => ({
      ...f,
      topic: q.topic ?? '',
      message_start_date: q.message_start_date ?? '',
      message_end_date: q.message_end_date ?? '',
      source: q.source ?? '',
      thread_id: q.thread_id ?? '',
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
      topic: form.topic || undefined,
      message_start_date: form.message_start_date || undefined,
      message_end_date: form.message_end_date || undefined,
      source: form.source || undefined,
      thread_id: form.thread_id || undefined,
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
    const toISO = (d: Date) => d.toISOString().split('T')[0]
    setForm({ ...form, message_start_date: toISO(start), message_end_date: toISO(end) })
  }

  function setThisMonth() {
    const now = new Date()
    const first = new Date(now.getFullYear(), now.getMonth(), 1)
    const last = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    const toISO = (d: Date) => d.toISOString().split('T')[0]
    setForm({ ...form, message_start_date: toISO(first), message_end_date: toISO(last) })
  }

  function copyToClipboard(text: string, e: React.MouseEvent<HTMLButtonElement>) {
    navigator.clipboard.writeText(text).then(() => {
      const btn = e.currentTarget
      const original = btn.textContent
      btn.textContent = 'Copied!'
      setTimeout(() => { if (btn) btn.textContent = original || 'Copy' }, 1500)
    })
  }

  function toggleSortOrder() {
    setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')
  }

  const prevDisabled = q.skip === 0
  const nextDisabled = isTopicSearch ? true : (data.count < (q.limit ?? 20))

  // If user lacks permissions, show access denied screen
  if (accessDenied) {
    return <AccessDenied message={accessDenied} />
  }

  return (
    <div>
      <h1>Reports</h1>
      <p className="subtitle">Browse and search summarization reports</p>

      <div className="filters">
        <h2>Filters &amp; Search</h2>
        <form onSubmit={applyFilters}>
          <div className="filter-section">
            <h3>🔍 Topic-Based Search</h3>
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="topic">Search by Topic or Keywords</label>
                <input id="topic" value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })} placeholder="e.g., consensus mechanisms, network performance" />
                <div className="help-text">Uses AI to find semantically related reports</div>
              </div>
            </div>
          </div>

          <div className="filter-section">
            <h3>📅 Thread Message Date Range</h3>
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="message_start_date">Start Date</label>
                <input type="date" id="message_start_date" value={form.message_start_date} onChange={e => setForm({ ...form, message_start_date: e.target.value })} />
              </div>
              <div className="filter-group">
                <label htmlFor="message_end_date">End Date</label>
                <input type="date" id="message_end_date" value={form.message_end_date} onChange={e => setForm({ ...form, message_end_date: e.target.value })} />
              </div>
            </div>
            <div className="help-text">Filters threads whose messages overlap with the selected date range (inclusive)</div>
            <div className="quick-dates">
              <button type="button" className="quick-date-btn" onClick={() => setDateRange(7)}>Last 7 days</button>
              <button type="button" className="quick-date-btn" onClick={() => setDateRange(30)}>Last 30 days</button>
              <button type="button" className="quick-date-btn" onClick={() => setDateRange(90)}>Last 90 days</button>
              <button type="button" className="quick-date-btn" onClick={setThisMonth}>This month</button>
            </div>
          </div>

          <div className="filter-section">
            <h3>📦 Source &amp; Thread</h3>
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="source">Archive Source</label>
                <select id="source" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}>
                  <option value="">All Sources</option>
                  {availableSources.map(src => (
                    <option key={src} value={src}>{src}</option>
                  ))}
                </select>
              </div>
              <div className="filter-group">
                <label htmlFor="thread_id">Thread ID</label>
                <input id="thread_id" value={form.thread_id} onChange={e => setForm({ ...form, thread_id: e.target.value })} placeholder="Specific thread ID" />
              </div>
            </div>
          </div>

          <div className="filter-section">
            <h3>📊 Thread Metadata</h3>
            <div className="filter-row">
              <div className="filter-group small">
                <label htmlFor="min_participants">Min Participants</label>
                <input type="number" id="min_participants" value={form.min_participants} onChange={e => setForm({ ...form, min_participants: e.target.value })} min={0} placeholder="0" />
              </div>
              <div className="filter-group small">
                <label htmlFor="max_participants">Max Participants</label>
                <input type="number" id="max_participants" value={form.max_participants} onChange={e => setForm({ ...form, max_participants: e.target.value })} min={0} placeholder="∞" />
              </div>
              <div className="filter-group small">
                <label htmlFor="min_messages">Min Messages</label>
                <input type="number" id="min_messages" value={form.min_messages} onChange={e => setForm({ ...form, min_messages: e.target.value })} min={0} placeholder="0" />
              </div>
              <div className="filter-group small">
                <label htmlFor="max_messages">Max Messages</label>
                <input type="number" id="max_messages" value={form.max_messages} onChange={e => setForm({ ...form, max_messages: e.target.value })} min={0} placeholder="∞" />
              </div>
            </div>
          </div>

          <div className="filter-section">
            <h3>⚙️ Display Options</h3>
            <div className="filter-row">
              <div className="filter-group small">
                <label htmlFor="limit">Results per page</label>
                <select id="limit" value={form.limit} onChange={e => setForm({ ...form, limit: e.target.value })}>
                  <option value="10">10</option>
                  <option value="20">20</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                </select>
              </div>
              <div className="filter-group" style={{ flex: 2 }}>
                <div className="button-group">
                  <button type="submit">Apply Filters</button>
                  <button type="button" className="clear-btn" onClick={clearAll}>Clear All</button>
                </div>
              </div>
            </div>
          </div>
        </form>
      </div>

      {(q.topic || q.message_start_date || q.message_end_date || q.source || q.thread_id || q.min_participants || q.max_participants || q.min_messages || q.max_messages) && (
        <div className="active-filters">
          <h3>Active Filters:</h3>
          <div className="filter-tags">
            {q.topic && <span className="filter-tag">Topic: {q.topic} <span className="remove" onClick={() => remove('topic')}>×</span></span>}
            {q.message_start_date && <span className="filter-tag">Messages from: {q.message_start_date} <span className="remove" onClick={() => remove('message_start_date')}>×</span></span>}
            {q.message_end_date && <span className="filter-tag">Messages until: {q.message_end_date} <span className="remove" onClick={() => remove('message_end_date')}>×</span></span>}
            {q.source && <span className="filter-tag">Source: {q.source} <span className="remove" onClick={() => remove('source')}>×</span></span>}
            {q.thread_id && (
              <span className="filter-tag">
                Thread: {q.thread_id!.length > 16 ? `${q.thread_id!.slice(0,16)}...` : q.thread_id}
                <span className="remove" onClick={() => remove('thread_id')}>×</span>
              </span>
            )}
            {q.min_participants && <span className="filter-tag">Min Participants: {q.min_participants} <span className="remove" onClick={() => remove('min_participants')}>×</span></span>}
            {q.max_participants && <span className="filter-tag">Max Participants: {q.max_participants} <span className="remove" onClick={() => remove('max_participants')}>×</span></span>}
            {q.min_messages && <span className="filter-tag">Min Messages: {q.min_messages} <span className="remove" onClick={() => remove('min_messages')}>×</span></span>}
            {q.max_messages && <span className="filter-tag">Max Messages: {q.max_messages} <span className="remove" onClick={() => remove('max_messages')}>×</span></span>}
          </div>
        </div>
      )}

      <div className="reports-table">
        {!loading && !error && data.reports.length > 0 && (
          <div style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
              📅 Sorted by: Thread Start Date ({sortOrder === 'desc' ? 'Newest First' : 'Oldest First'})
            </span>
            <button 
              className="quick-date-btn" 
              onClick={toggleSortOrder}
              style={{ padding: '4px 12px', fontSize: '13px' }}
            >
              {sortOrder === 'desc' ? '↓ Newest First' : '↑ Oldest First'}
            </button>
          </div>
        )}
        {loading ? (
          <div className="no-reports">Loading…</div>
        ) : error ? (
          <div className="no-reports">{error}</div>
        ) : data.reports.length === 0 ? (
          <div className="no-reports">
            <p>No reports match the selected filters.</p>
            {(q.topic || q.message_start_date || q.message_end_date || q.source || q.thread_id) && (
              <p><button className="clear-btn" onClick={clearAll}>Clear Filters</button></p>
            )}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Thread ID</th>
                <th>Thread Started</th>
                {isTopicSearch && <th>Relevance</th>}
                <th>Generated</th>
                <th>Source &amp; Metadata</th>
                <th>Summary Preview</th>
                <th>Citations</th>
              </tr>
            </thead>
            <tbody>
              {data.reports.map((r) => (
                <tr key={r._id}>
                  <td>
                    <Link className="report-link" to={`/reports/${r._id}`}>{r._id.slice(0,8)}...</Link>
                    <button className="copy-btn" onClick={(e) => copyToClipboard(r._id, e)}>Copy</button>
                  </td>
                  <td>
                    <div className="thread-id" title={r.thread_id}>{r.thread_id}</div>
                    <button className="copy-btn" onClick={(e) => copyToClipboard(r.thread_id, e)}>Copy</button>
                  </td>
                  <td className="timestamp">
                    {r.thread_metadata?.first_message_date 
                      ? new Date(r.thread_metadata.first_message_date).toLocaleDateString()
                      : 'N/A'}
                  </td>
                  {isTopicSearch && (
                    <td>
                      {typeof r.relevance_score === 'number' && (
                        <>
                          <span className="badge score">{(r.relevance_score * 100).toFixed(2)}%</span>
                          <div className="metadata">{r.matching_chunks} chunks</div>
                        </>
                      )}
                    </td>
                  )}
                  <td className="timestamp">{r.generated_at.slice(0,10)}</td>
                  <td>
                    {r.archive_metadata?.source && (
                      <span className="badge source">{r.archive_metadata.source}</span>
                    )}
                    {r.thread_metadata && (
                      <div className="metadata">👥 {r.thread_metadata.participant_count} participants • 💬 {r.thread_metadata.message_count} messages</div>
                    )}
                    {r.thread_metadata?.subject && (
                      <div className="metadata" style={{ marginTop: 4 }}>
                        <strong>Subject:</strong> {r.thread_metadata.subject.length > 50 ? `${r.thread_metadata.subject.slice(0,50)}...` : r.thread_metadata.subject}
                      </div>
                    )}
                  </td>
                  <td className="summary-preview" title={r.content_markdown}>{(r.content_markdown ?? '').slice(0,100)}...</td>
                  <td>
                    <span className="badge">{r.citations?.length ?? 0} citations</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!isTopicSearch && (
        <div className="pagination">
          <button className={prevDisabled ? 'disabled' : ''} onClick={() => !prevDisabled && update({ skip: Math.max(0, (q.skip ?? 0) - (q.limit ?? 20)) })}>
            ← Previous
          </button>
          <span>Showing {(q.skip ?? 0) + 1} - {(q.skip ?? 0) + data.count} ({data.count} reports)</span>
          <button className={nextDisabled ? 'disabled' : ''} onClick={() => !nextDisabled && update({ skip: (q.skip ?? 0) + (q.limit ?? 20) })}>
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
