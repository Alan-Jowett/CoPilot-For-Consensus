// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchThread, fetchThreadMessages, Thread, Message, copy } from '../api'

export function ThreadDetail() {
  const { threadId } = useParams()
  const [searchParams] = useSearchParams()
  const highlightMessageId = searchParams.get('highlight')
  
  const [thread, setThread] = useState<Thread | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const limit = 50

  useEffect(() => {
    if (!threadId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    
    Promise.all([
      fetchThread(threadId),
      fetchThreadMessages(threadId, limit, page * limit)
    ])
      .then(([threadData, messagesData]) => {
        if (!cancelled) {
          setThread(threadData)
          setMessages(messagesData.messages)
          setHasMore(messagesData.messages.length >= limit)
        }
      })
      .catch(e => {
        if (!cancelled) setError(e?.message || 'Failed to load thread')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    
    return () => { cancelled = true }
  }, [threadId, page])

  // Scroll to highlighted message
  useEffect(() => {
    if (highlightMessageId && messages.length > 0) {
      const element = document.getElementById(`message-${highlightMessageId}`)
      if (element) {
        setTimeout(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 100)
      }
    }
  }, [highlightMessageId, messages])

  // Check if highlighted message exists in current page
  const highlightedMessageFound = highlightMessageId 
    ? messages.some(msg => msg.message_id === highlightMessageId)
    : true

  if (loading && !thread) return <div className="no-reports">Loading…</div>
  if (error === 'NOT_FOUND') return <div className="no-reports">Thread not found</div>
  if (error) return <div className="no-reports">{error}</div>
  if (!thread) return null

  return (
    <div>
      <Link to="/reports" className="back-link">← Back to Reports</Link>
      <h1>Thread Details</h1>

      <div className="thread-header">
        <div className="info-grid">
          <div className="info-item">
            <div className="info-label">Thread ID</div>
            <div className="info-value">
              {thread.thread_id}
              <button className="copy-btn" onClick={() => copy(thread.thread_id)}>Copy</button>
            </div>
          </div>
          {thread.subject && (
            <div className="info-item">
              <div className="info-label">Subject</div>
              <div className="info-value">{thread.subject}</div>
            </div>
          )}
          <div className="info-item">
            <div className="info-label">Messages</div>
            <div className="info-value">{thread.message_count ?? messages.length}</div>
          </div>
          {thread.participants && thread.participants.length > 0 && (
            <div className="info-item">
              <div className="info-label">Participants</div>
              <div className="info-value">{thread.participants.length}</div>
            </div>
          )}
          {thread.first_message_date && (
            <div className="info-item">
              <div className="info-label">First Message</div>
              <div className="info-value">{new Date(thread.first_message_date).toLocaleDateString()}</div>
            </div>
          )}
          {thread.last_message_date && (
            <div className="info-item">
              <div className="info-label">Last Message</div>
              <div className="info-value">{new Date(thread.last_message_date).toLocaleDateString()}</div>
            </div>
          )}
        </div>
        
        {thread.summary_id && (
          <div style={{ marginTop: '15px' }}>
            <Link className="view-summary-btn" to={`/reports/${thread.summary_id}`}>
              📄 View Summary Report
            </Link>
          </div>
        )}
      </div>

      <div className="messages-section">
        <h2>Messages ({messages.length})</h2>
        {highlightMessageId && !highlightedMessageFound && (
          <div className="highlight-warning">
            ⚠️ The highlighted message may be on a different page. Use pagination to find it.
          </div>
        )}
        {messages.length === 0 ? (
          <div className="no-reports">No messages found in this thread.</div>
        ) : (
          <div className="messages-list">
            {messages.map((msg) => {
              const isHighlighted = highlightMessageId && msg.message_id === highlightMessageId
              return (
                <div
                  key={msg._id}
                  id={`message-${msg.message_id}`}
                  className={`message-card ${isHighlighted ? 'highlighted' : ''}`}
                >
                  <div className="message-header">
                    <div className="message-meta">
                      <span className="message-sender">{msg.from ? `${msg.from.name || msg.from.email}` : 'Unknown Sender'}</span>
                      {msg.date && (
                        <span className="message-date">
                          {new Date(msg.date).toLocaleString()}
                        </span>
                      )}
                    </div>
                    {isHighlighted && (
                      <span className="highlight-badge">Referenced in Summary</span>
                    )}
                  </div>
                  
                  {msg.subject && msg.subject !== thread.subject && (
                    <div className="message-subject">{msg.subject}</div>
                  )}
                  
                  <div className="message-body-preview">
                    {(msg.body_normalized || '').substring(0, 300)}
                    {(msg.body_normalized || '').length > 300 && '...'}
                  </div>
                  
                  <div className="message-footer">
                    <Link 
                      className="view-message-link" 
                      to={`/messages/${msg._id}`}
                    >
                      View Full Message →
                    </Link>
                    <span className="message-id-display">
                      ID: {msg.message_id.substring(0, 20)}...
                      <button className="copy-btn-small" onClick={() => copy(msg.message_id)}>Copy</button>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        
        {(page > 0 || hasMore) && (
          <div className="pagination">
            <button 
              className={page === 0 ? 'disabled' : ''}
              onClick={() => page > 0 && setPage(page - 1)}
            >
              ← Previous
            </button>
            <span>Page {page + 1}</span>
            <button 
              className={!hasMore ? 'disabled' : ''}
              onClick={() => hasMore && setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
