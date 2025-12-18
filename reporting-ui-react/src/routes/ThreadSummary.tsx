// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchThreadSummary, Report } from '../api'
import ReactMarkdown from 'react-markdown'

export function ThreadSummary() {
  const { threadId } = useParams()
  const [summary, setSummary] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!threadId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchThreadSummary(threadId)
      .then(r => { if (!cancelled) setSummary(r) })
      .catch(e => { if (!cancelled) setError(e?.message || 'Failed to load summary') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [threadId])

  function copy(text: string) { navigator.clipboard.writeText(text) }

  if (loading) return <div className="no-reports">Loading…</div>
  if (error === 'NOT_FOUND') return <div className="no-reports">No summary found for thread</div>
  if (error) return <div className="no-reports">{error}</div>
  if (!summary) return null

  return (
    <div>
      <Link to="/reports" className="back-link">← Back to Reports</Link>
      <h1>Thread Summary</h1>

      <div className="thread-info">
        <div className="info-label">Thread ID</div>
        <div className="info-value">
          {summary.thread_id}
          <button className="copy-btn" onClick={() => copy(summary.thread_id)}>Copy</button>
        </div>
      </div>

      <div className="summary-section">
        <h2>Latest Summary</h2>
        <div className="markdown">
          <ReactMarkdown>{summary.content_markdown || ''}</ReactMarkdown>
        </div>
        <Link className="detail-link" to={`/reports/${summary._id}`}>View Full Report Details →</Link>
      </div>
    </div>
  )
}
