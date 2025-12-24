// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchIngestionSources, deleteIngestionSource, triggerIngestionSource, IngestionSource } from '../api'
import { ConfirmDialog } from '../components/ConfirmDialog'

export function SourcesList() {
  const navigate = useNavigate()
  const [sources, setSources] = useState<IngestionSource[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [sourceToDelete, setSourceToDelete] = useState<string | null>(null)

  const loadSources = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchIngestionSources()
      setSources(data.sources)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to load sources'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSources()
  }, [])

  const handleDeleteClick = (name: string) => {
    setSourceToDelete(name)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!sourceToDelete) return

    setDeleteDialogOpen(false)

    try {
      await deleteIngestionSource(sourceToDelete)
      setSuccessMessage(`Source "${sourceToDelete}" deleted successfully`)
      setTimeout(() => setSuccessMessage(null), 3000)
      await loadSources()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to delete source'
      setError(message)
    } finally {
      setSourceToDelete(null)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setSourceToDelete(null)
  }

  const handleTrigger = async (name: string) => {
    try {
      const result = await triggerIngestionSource(name)
      setSuccessMessage(result.message || `Ingestion triggered for "${name}"`)
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to trigger ingestion'
      setError(message)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Ingestion Sources</h1>
          <p className="subtitle">Manage email ingestion sources and configurations</p>
        </div>
        <Link to="/sources/new" className="view-thread-btn">
          ➕ Add New Source
        </Link>
      </div>

      {successMessage && (
        <div className="success-message">{successMessage}</div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="reports-table">
        {loading ? (
          <div className="no-reports">Loading…</div>
        ) : sources.length === 0 ? (
          <div className="no-reports">
            <p>No ingestion sources configured yet.</p>
            <p>
              <Link to="/sources/new" className="view-thread-btn">Add Your First Source</Link>
            </p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>URL/Connection</th>
                <th>Status</th>
                <th>Schedule</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr key={source.name}>
                  <td>
                    <strong>{source.name}</strong>
                  </td>
                  <td>
                    <span className="badge source">{source.source_type}</span>
                  </td>
                  <td className="summary-preview" title={source.url}>
                    {source.url}
                    {source.folder && <div className="metadata">Folder: {source.folder}</div>}
                  </td>
                  <td>
                    <span className={`badge ${source.enabled ? 'enabled' : 'disabled'}`}>
                      {source.enabled ? '✓ Enabled' : '✗ Disabled'}
                    </span>
                  </td>
                  <td>
                    <span className="metadata">{source.schedule || 'Manual only'}</span>
                  </td>
                  <td>
                    <div className="action-buttons">
                      <button
                        className="action-btn edit"
                        onClick={() => navigate(`/sources/edit/${encodeURIComponent(source.name)}`)}
                        title="Edit source"
                      >
                        ✏️ Edit
                      </button>
                      <button
                        className="action-btn trigger"
                        onClick={() => handleTrigger(source.name)}
                        title="Trigger ingestion now"
                      >
                        ▶️ Trigger
                      </button>
                      <button
                        className="action-btn delete"
                        onClick={() => handleDeleteClick(source.name)}
                        title="Delete source"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmDialog
        isOpen={deleteDialogOpen}
        title="Delete Ingestion Source"
        message={
          sourceToDelete
            ? `Are you sure you want to delete source "${sourceToDelete}"? This action cannot be undone.`
            : 'Are you sure you want to delete this source? This action cannot be undone.'
        }
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        confirmText="Delete"
        cancelText="Cancel"
        confirmButtonClass="delete"
      />
    </div>
  )
}
