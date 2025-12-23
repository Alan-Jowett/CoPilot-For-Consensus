// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchMessage, fetchMessageChunks, Message, Chunk, copy } from '../api'
import ReactMarkdown from 'react-markdown'

export function MessageDetail() {
  const { messageDocId } = useParams()
  const [message, setMessage] = useState<Message | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!messageDocId) return
    let cancelled = false
    setLoading(true)
    setError(null)

    fetchMessage(messageDocId)
      .then(async (msgData) => {
        if (!cancelled) {
          setMessage(msgData)
          // Fetch chunks for this message
          if (msgData.message_id) {
            try {
              const chunksData = await fetchMessageChunks(msgData.message_id)
              if (!cancelled) {
                setChunks(chunksData.chunks)
              }
            } catch (e) {
              // Chunks are optional, don't fail if they're not available
              console.warn('Failed to fetch chunks:', e)
            }
          }
        }
      })
      .catch(e => {
        if (!cancelled) setError(e?.message || 'Failed to load message')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [messageDocId])

  if (loading) return <div className="no-reports">Loading…</div>
  if (error === 'NOT_FOUND') return <div className="no-reports">Message not found</div>
  if (error) return <div className="no-reports">{error}</div>
  if (!message) return null

  return (
    <div>
      {message.thread_id && (
        <Link to={`/threads/${message.thread_id}/messages`} className="back-link">
          ← Back to Thread
        </Link>
      )}
      <h1>Message Details</h1>

      <div className="message-detail-header">
        <div className="info-grid">
          <div className="info-item">
            <div className="info-label">Message ID</div>
            <div className="info-value">
              {message.message_id || 'unknown'}
              <button className="copy-btn" onClick={() => copy(message.message_id || 'unknown')}>Copy</button>
            </div>
          </div>
          {message.from && message.from.email && (
            <div className="info-item">
              <div className="info-label">From</div>
              <div className="info-value">
                {message.from.name && message.from.name.trim()
                  ? `${message.from.name} <${message.from.email}>`
                  : message.from.email}
              </div>
            </div>
          )}
          {message.date && (
            <div className="info-item">
              <div className="info-label">Date</div>
              <div className="info-value">{new Date(message.date).toLocaleString()}</div>
            </div>
          )}
          {message.subject && (
            <div className="info-item">
              <div className="info-label">Subject</div>
              <div className="info-value">{message.subject}</div>
            </div>
          )}
        </div>
      </div>

      <div className="message-body-section">
        <h2>Message Body</h2>
        <div className="message-body-content">
          <ReactMarkdown>{message.body_normalized || 'No message body available.'}</ReactMarkdown>
        </div>
      </div>

      {chunks.length > 0 && (
        <div className="chunks-section">
          <h2>Extracted Chunks ({chunks.length})</h2>
          <p className="section-description">
            These are the text chunks extracted from this message for embedding and retrieval.
          </p>
          <div className="chunks-list">
            {chunks.map((chunk, idx) => (
              <div key={chunk._id} className="chunk-card">
                <div className="chunk-header">
                  <span className="chunk-number">Chunk #{idx + 1}</span>
                  <span className="chunk-id-badge">{(chunk.chunk_id || 'unknown').substring(0, 16)}...</span>
                </div>
                <div className="chunk-text">{chunk.text}</div>
                {(chunk.offset !== undefined || chunk.length !== undefined) && (
                  <div className="chunk-metadata">
                    {chunk.offset !== undefined && (
                      <span>Offset: {chunk.offset}</span>
                    )}
                    {chunk.length !== undefined && (
                      <span>Length: {chunk.length}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {message.headers && Object.keys(message.headers).length > 0 && (
        <div className="headers-section">
          <h2>Message Headers</h2>
          <div className="headers-list">
            {Object.entries(message.headers).map(([key, value]) => (
              <div key={key} className="header-item">
                <span className="header-key">{key}:</span>
                <span className="header-value">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
