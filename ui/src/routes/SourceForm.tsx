// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchIngestionSource, createIngestionSource, updateIngestionSource, uploadMailboxFile, IngestionSource } from '../api'
import { AccessDenied } from '../components/AccessDenied'

const SOURCE_TYPES = ['local', 'rsync', 'http', 'imap']

export function SourceForm() {
  const { sourceName } = useParams()
  const navigate = useNavigate()
  const isEditMode = !!sourceName

  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [accessDenied, setAccessDenied] = useState<string | null>(null)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const [form, setForm] = useState<IngestionSource>({
    name: '',
    source_type: 'local',
    url: '',
    port: undefined,
    username: '',
    password: '',
    folder: '',
    enabled: true,
    schedule: '',
  })

  useEffect(() => {
    if (!isEditMode) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setAccessDenied(null)

    fetchIngestionSource(sourceName!)
      .then(source => {
        if (!cancelled) {
          setForm({
            ...source,
            // Ensure optional fields have default empty string values for controlled inputs
            username: source.username || '',
            password: source.password || '',
            folder: source.folder || '',
            schedule: source.schedule || '',
          })
        }
      })
      .catch(e => {
        if (!cancelled) {
          if (e?.message?.startsWith('ACCESS_DENIED:')) {
            setAccessDenied(e.message.replace('ACCESS_DENIED: ', ''))
            return
          }
          const message =
            e instanceof Error && e.message === 'NOT_FOUND'
              ? 'Source not found'
              : 'Failed to load source'
          setError(message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [sourceName, isEditMode])

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}

    if (!form.name.trim()) {
      errors.name = 'Source name is required'
    }

    if (!form.source_type) {
      errors.source_type = 'Source type is required'
    }

    if (!form.url.trim()) {
      errors.url = 'URL/connection string is required'
    }

    if (form.source_type === 'imap') {
      if (!form.port) {
        errors.port = 'Port is required for IMAP sources'
      }
      if (!form.username?.trim()) {
        errors.username = 'Username is required for IMAP sources'
      }
      if (!form.password?.trim()) {
        errors.password = 'Password is required for IMAP sources'
      }
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setUploadProgress(0)
    setError(null)

    try {
      const response = await uploadMailboxFile(file, (percent) => {
        setUploadProgress(percent)
      })

      // Auto-fill the URL field with the server path
      setForm({ ...form, url: response.server_path })
      setUploadProgress(100)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Upload failed'
      setError(message)
    } finally {
      setUploading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    setSaving(true)
    setError(null)

    try {
      // Prepare the source data, removing empty optional fields
      const sourceData: IngestionSource = {
        name: form.name.trim(),
        source_type: form.source_type,
        url: form.url.trim(),
        enabled: form.enabled,
      }

      if (form.port) sourceData.port = form.port
      if (form.username?.trim()) sourceData.username = form.username.trim()
      if (form.password?.trim()) sourceData.password = form.password.trim()
      if (form.folder?.trim()) sourceData.folder = form.folder.trim()
      if (form.schedule?.trim()) sourceData.schedule = form.schedule.trim()

      if (isEditMode) {
        await updateIngestionSource(sourceName!, sourceData)
      } else {
        await createIngestionSource(sourceData)
      }

      navigate('/sources')
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to save source'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  if (accessDenied) {
    return <AccessDenied message={accessDenied} />
  }

  if (loading) {
    return <div className="no-reports">Loading…</div>
  }

  if (error && isEditMode) {
    return (
      <div>
        <Link to="/sources" className="back-link">← Back to Sources</Link>
        <div className="no-reports">{error}</div>
      </div>
    )
  }

  return (
    <div>
      <Link to="/sources" className="back-link">← Back to Sources</Link>
      <h1>{isEditMode ? 'Edit Source' : 'Add New Source'}</h1>
      <p className="subtitle">
        {isEditMode
          ? `Update configuration for source "${sourceName}"`
          : 'Configure a new ingestion source for email archives'}
      </p>

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="filters">
        <form onSubmit={handleSubmit}>
          <div className="filter-section">
            <h3>Basic Information</h3>
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="name">
                  Source Name <span className="required">*</span>
                </label>
                <input
                  id="name"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g., my-mailbox"
                  disabled={isEditMode}
                  className={validationErrors.name ? 'input-error' : ''}
                />
                {validationErrors.name && <div className="field-error">{validationErrors.name}</div>}
                {isEditMode && <div className="help-text">Source name cannot be changed</div>}
              </div>
              <div className="filter-group">
                <label htmlFor="source_type">
                  Source Type <span className="required">*</span>
                </label>
                <select
                  id="source_type"
                  value={form.source_type}
                  onChange={e => setForm({ ...form, source_type: e.target.value })}
                  className={validationErrors.source_type ? 'input-error' : ''}
                >
                  {SOURCE_TYPES.map(type => (
                    <option key={type} value={type}>
                      {type.toUpperCase()}
                    </option>
                  ))}
                </select>
                {validationErrors.source_type && <div className="field-error">{validationErrors.source_type}</div>}
              </div>
            </div>
          </div>

          <div className="filter-section">
            <h3>Connection Details</h3>

            {form.source_type === 'local' && !isEditMode && (
              <div className="filter-row">
                <div className="filter-group">
                  <label htmlFor="file_upload">
                    Upload Mailbox File (Optional)
                  </label>
                  <input
                    type="file"
                    id="file_upload"
                    accept=".mbox,.zip,.tar,.tar.gz,.tgz"
                    onChange={handleFileUpload}
                    disabled={uploading}
                  />
                  <div className="help-text">
                    Upload a .mbox, .zip, or .tar file (max 100MB). The server path will be auto-filled.
                  </div>
                  {uploading && (
                    <div className="upload-progress">
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                      </div>
                      <div className="progress-text">{uploadProgress}%</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="url">
                  URL / Connection String <span className="required">*</span>
                </label>
                <input
                  id="url"
                  value={form.url}
                  onChange={e => setForm({ ...form, url: e.target.value })}
                  placeholder={
                    form.source_type === 'imap'
                      ? 'e.g., imap.example.com'
                      : form.source_type === 'http'
                      ? 'e.g., https://example.com/archives'
                      : form.source_type === 'rsync'
                      ? 'e.g., user@host:/path/to/archives'
                      : 'e.g., /path/to/local/archive.mbox'
                  }
                  className={validationErrors.url ? 'input-error' : ''}
                />
                {validationErrors.url && <div className="field-error">{validationErrors.url}</div>}
              </div>
              {form.source_type === 'imap' && (
                <div className="filter-group small">
                  <label htmlFor="port">
                    Port <span className="required">*</span>
                  </label>
                  <input
                    type="number"
                    id="port"
                    value={form.port || ''}
                    onChange={e => setForm({ ...form, port: e.target.value ? Number(e.target.value) : undefined })}
                    placeholder="993"
                    className={validationErrors.port ? 'input-error' : ''}
                  />
                  {validationErrors.port && <div className="field-error">{validationErrors.port}</div>}
                </div>
              )}
            </div>
          </div>

          {form.source_type === 'imap' && (
            <div className="filter-section">
              <h3>Authentication</h3>
              <div className="filter-row">
                <div className="filter-group">
                  <label htmlFor="username">
                    Username <span className="required">*</span>
                  </label>
                  <input
                    id="username"
                    value={form.username || ''}
                    onChange={e => setForm({ ...form, username: e.target.value })}
                    placeholder="user@example.com"
                    autoComplete="username"
                    className={validationErrors.username ? 'input-error' : ''}
                  />
                  {validationErrors.username && <div className="field-error">{validationErrors.username}</div>}
                </div>
                <div className="filter-group">
                  <label htmlFor="password">
                    Password <span className="required">*</span>
                  </label>
                  <input
                    type="password"
                    id="password"
                    value={form.password || ''}
                    onChange={e => setForm({ ...form, password: e.target.value })}
                    placeholder="••••••••"
                    autoComplete={isEditMode ? "current-password" : "new-password"}
                    className={validationErrors.password ? 'input-error' : ''}
                  />
                  {validationErrors.password && <div className="field-error">{validationErrors.password}</div>}
                </div>
              </div>
              <div className="filter-row">
                <div className="filter-group">
                  <label htmlFor="folder">Folder Path (optional)</label>
                  <input
                    id="folder"
                    value={form.folder || ''}
                    onChange={e => setForm({ ...form, folder: e.target.value })}
                    placeholder="INBOX"
                  />
                  <div className="help-text">IMAP folder to read from (default: INBOX)</div>
                </div>
              </div>
            </div>
          )}

          <div className="filter-section">
            <h3>Scheduling & Options</h3>
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="schedule">Schedule (Cron Expression)</label>
                <input
                  id="schedule"
                  value={form.schedule || ''}
                  onChange={e => setForm({ ...form, schedule: e.target.value })}
                  placeholder="e.g., 0 */6 * * * (every 6 hours)"
                />
                <div className="help-text">Leave empty for manual trigger only</div>
              </div>
              <div className="filter-group small">
                <label htmlFor="enabled" className="checkbox-label">
                  <input
                    type="checkbox"
                    id="enabled"
                    checked={form.enabled}
                    onChange={e => setForm({ ...form, enabled: e.target.checked })}
                  />
                  <span>Enabled</span>
                </label>
                <div className="help-text">Enable automatic ingestion</div>
              </div>
            </div>
          </div>

          <div className="button-group">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving…' : (isEditMode ? 'Update Source' : 'Create Source')}
            </button>
            <button type="button" className="cancel-btn" onClick={() => navigate('/sources')}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
