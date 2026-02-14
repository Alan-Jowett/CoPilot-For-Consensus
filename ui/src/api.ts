// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

import { getUnauthorizedCallback } from './contexts/AuthContext'

// NOTE: Auth tokens are now stored in httpOnly cookies (not localStorage)
// This protects against XSS attacks since JavaScript cannot access httpOnly cookies.
// The browser automatically sends cookies with requests when credentials: 'include' is set.

export function setUnauthorizedCallback(callback: (() => void) | null) {
  // Note: This is handled in AuthContext now, but keeping for backward compatibility
}

// Helper to make authenticated API requests
// Uses httpOnly cookies for authentication (sent automatically by browser)
async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {})

  console.log('[fetchWithAuth] URL:', url, 'Using cookie-based auth')

  // Send cookies with the request (includes httpOnly auth_token cookie)
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include'  // Always include cookies for authentication
  })

  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    console.log('[fetchWithAuth] Got 401, redirecting to login')
    const callback = getUnauthorizedCallback()
    if (callback) {
      callback()
    }
    throw new Error('UNAUTHORIZED')
  }

  // Handle 403 Forbidden - user lacks required permissions
  // Unlike 401 (expired token), 403 means the token is valid but the user doesn't have access
  // DO NOT trigger token refresh for 403 - this would cause an infinite loop
  if (response.status === 403) {
    console.log('[fetchWithAuth] Got 403 Forbidden - user lacks required permissions')
    let errorDetail = 'You do not have permission to access this resource.'
    try {
      const errorData = await response.json()
      if (errorData.detail) {
        errorDetail = errorData.detail
      }
    } catch (e) {
      // Couldn't parse error response, use default message
    }
    throw new Error(`ACCESS_DENIED: ${errorDetail}`)
  }

  return response
}

// Helper to format error messages from API responses
// Ensures error.detail is always converted to a readable string
interface ApiErrorLike {
  detail?: unknown
}

function isApiErrorLike(error: unknown): error is ApiErrorLike {
  return (
    typeof error === 'object' &&
    error != null &&
    Object.prototype.hasOwnProperty.call(error, 'detail')
  )
}

function formatErrorMessage(error: unknown, fallbackMessage: string): string {
  if (isApiErrorLike(error)) {
    if (typeof error.detail === 'string') {
      return error.detail
    }
    if (error.detail !== undefined) {
      try {
        return JSON.stringify(error.detail)
      } catch (e) {
        // If JSON.stringify fails (e.g., circular references), fall through to fallback message
        console.warn('Failed to stringify error.detail:', error.detail, 'Error:', e)
      }
    }
  }
  return fallbackMessage
}

export interface Report {
  _id: string
  thread_id: string
  generated_at: string
  generated_by?: string
  content_markdown: string
  citations: Array<{ message_id?: string; chunk_id?: string; quote?: string | null }>
  archive_metadata?: { source?: string | null } | null
  thread_metadata?: {
    participant_count?: number
    message_count?: number
    subject?: string
    first_message_date?: string
    last_message_date?: string
  } | null
  relevance_score?: number
  matching_chunks?: number
  metadata?: {
    llm_model?: string
    tokens_prompt?: number
    tokens_completion?: number
    latency_ms?: number
  }
}

export interface Thread {
  _id: string
  thread_id: string
  subject?: string
  participants?: string[]
  message_count?: number
  first_message_date?: string
  last_message_date?: string
  archive_id?: string
  archive_source?: string
  summary_id?: string
}

export interface Message {
  _id: string
  message_id?: string
  thread_id: string
  subject?: string
  from?: { name: string; email: string }
  date?: string
  body_normalized?: string
  headers?: Record<string, string>
  chunk_count?: number
}

export interface Chunk {
  _id: string
  chunk_id?: string
  message_id: string
  message_doc_id?: string
  thread_id: string
  text: string
  offset?: number
  length?: number
}

export interface ReportsListResponse {
  reports: Report[]
  count: number
}

// If VITE_REPORTING_API_URL is not set, use an environment-aware default base path:
// - In Vite dev mode, default to same-origin root ('') for standalone UI development,
//   allowing the UI's internal nginx to proxy requests to the reporting service.
// - In production, default to same-origin gateway subpath ('/reporting'), assuming the UI
//   is accessed via the API gateway that mounts reporting at /reporting.
// - To override this assumption in non-gateway deployments, set VITE_REPORTING_API_URL
//   at build time (e.g., VITE_REPORTING_API_URL=http://localhost:8080 npm run build).
const DEFAULT_API = import.meta.env.DEV ? '' : '/reporting'
const base = import.meta.env.VITE_REPORTING_API_URL || DEFAULT_API

export function reportingApiBase(): string {
  return base
}

export async function fetchSources(): Promise<string[]> {
  const r = await fetchWithAuth(`${base}/api/sources`)
  if (!r.ok) throw new Error(`Sources fetch failed: ${r.status}`)
  const data = await r.json()
  return data.sources ?? []
}

export interface ReportsQuery {
  thread_id?: string
  topic?: string
  message_start_date?: string  // Filter by thread message dates (inclusive overlap)
  message_end_date?: string    // Filter by thread message dates (inclusive overlap)
  source?: string
  min_participants?: string
  max_participants?: string
  min_messages?: string
  max_messages?: string
  limit?: number
  skip?: number
  sort_by?: string
  sort_order?: string
}

function toQuery(params: Record<string, any>): string {
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && `${v}`.length > 0) sp.set(k, String(v))
  })
  return sp.toString()
}

export async function fetchReports(q: ReportsQuery): Promise<ReportsListResponse> {
  const params: any = {
    limit: q.limit ?? 20,
    skip: q.skip ?? 0,
  }
  if (q.thread_id) params.thread_id = q.thread_id
  if (q.message_start_date) params.message_start_date = q.message_start_date
  if (q.message_end_date) params.message_end_date = q.message_end_date
  if (q.source) params.source = q.source
  if (q.min_participants) params.min_participants = q.min_participants
  if (q.max_participants) params.max_participants = q.max_participants
  if (q.min_messages) params.min_messages = q.min_messages
  if (q.max_messages) params.max_messages = q.max_messages
  if (q.sort_by) params.sort_by = q.sort_by
  if (q.sort_order) params.sort_order = q.sort_order

  const url = `${base}/api/reports?${toQuery(params)}`
  const r = await fetchWithAuth(url)
  if (!r.ok) throw new Error(`Reports fetch failed: ${r.status}`)
  return r.json()
}

export async function searchReportsByTopic(topic: string, limit = 20): Promise<Report[]> {
  const params = toQuery({ topic, limit, min_score: 0.5 })
  const r = await fetchWithAuth(`${base}/api/reports/search?${params}`)
  if (!r.ok) throw new Error(`Topic search failed: ${r.status}`)
  const data = await r.json()
  return data.reports ?? []
}

export async function fetchReport(id: string): Promise<Report> {
  const r = await fetchWithAuth(`${base}/api/reports/${id}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Report fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThreadSummary(threadId: string): Promise<Report> {
  const r = await fetchWithAuth(`${base}/api/threads/${threadId}/summary`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Thread summary fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThread(threadId: string): Promise<Thread> {
  const r = await fetchWithAuth(`${base}/api/threads/${threadId}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Thread fetch failed: ${r.status}`)
  return r.json()
}

export interface ThreadsQuery {
  message_start_date?: string  // Filter by thread message dates (inclusive overlap)
  message_end_date?: string    // Filter by thread message dates (inclusive overlap)
  source?: string
  min_participants?: string
  max_participants?: string
  min_messages?: string
  max_messages?: string
  limit?: number
  skip?: number
  sort_by?: string
  sort_order?: string
}

export interface ThreadsListResponse {
  threads: Thread[]
  count: number
}

export async function fetchThreadsList(q: ThreadsQuery): Promise<ThreadsListResponse> {
  const params: Record<string, string | number> = {
    limit: q.limit ?? 20,
    skip: q.skip ?? 0,
  }
  if (q.message_start_date) params.message_start_date = q.message_start_date
  if (q.message_end_date) params.message_end_date = q.message_end_date
  if (q.source) params.source = q.source
  if (q.min_participants) params.min_participants = q.min_participants
  if (q.max_participants) params.max_participants = q.max_participants
  if (q.min_messages) params.min_messages = q.min_messages
  if (q.max_messages) params.max_messages = q.max_messages
  if (q.sort_by) params.sort_by = q.sort_by
  if (q.sort_order) params.sort_order = q.sort_order

  const url = `${base}/api/threads?${toQuery(params)}`
  const r = await fetchWithAuth(url)
  if (!r.ok) throw new Error(`Threads fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThreadMessages(
  threadId: string,
  limit = 100,
  skip = 0
): Promise<{ messages: Message[]; count: number }> {
  const params = toQuery({ thread_id: threadId, limit, skip })
  const r = await fetchWithAuth(`${base}/api/messages?${params}`)
  if (!r.ok) throw new Error(`Messages fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchMessage(messageDocId: string): Promise<Message> {
  const r = await fetchWithAuth(`${base}/api/messages/${messageDocId}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Message fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchMessageChunks(
  messageId: string,
  limit = 100
): Promise<{ chunks: Chunk[]; count: number }> {
  const params = toQuery({ message_id: messageId, limit })
  const r = await fetchWithAuth(`${base}/api/chunks?${params}`)
  if (!r.ok) throw new Error(`Chunks fetch failed: ${r.status}`)
  return r.json()
}

export function copy(text: string) {
  return navigator.clipboard.writeText(text)
}

// Ingestion Source Management API

export interface IngestionSource {
  name: string
  source_type: string
  url: string
  port?: number
  username?: string
  password?: string
  folder?: string
  enabled: boolean
  schedule?: string
}

export interface IngestionSourceStatus {
  name: string
  enabled: boolean
  last_run_at?: string
  last_run_status?: string
  last_error?: string
  next_run_at?: string
  files_processed: number
  files_skipped: number
}

export interface IngestionSourcesListResponse {
  sources: IngestionSource[]
  count: number
}

const INGESTION_API_BASE = '/ingestion'

export async function fetchIngestionSources(enabledOnly = false): Promise<IngestionSourcesListResponse> {
  const params = enabledOnly ? '?enabled_only=true' : ''
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources${params}`)
  if (!r.ok) throw new Error(`Failed to fetch sources: ${r.status}`)
  return r.json()
}

export async function fetchIngestionSource(name: string): Promise<IngestionSource> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to fetch source: ${r.status}`)
  return r.json()
}

export async function createIngestionSource(source: IngestionSource): Promise<{ message: string; source: IngestionSource }> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source),
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to create source: ${r.status}`))
  }
  return r.json()
}

export async function updateIngestionSource(name: string, source: IngestionSource): Promise<{ message: string; source: IngestionSource }> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source),
  })
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to update source: ${r.status}`))
  }
  return r.json()
}

export async function deleteIngestionSource(name: string): Promise<{ message: string }> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to delete source: ${r.status}`)
  return r.json()
}

export async function triggerIngestionSource(name: string): Promise<{ source_name: string; status: string; message: string; triggered_at: string }> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}/trigger`, {
    method: 'POST',
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to trigger ingestion: ${r.status}`))
  }
  return r.json()
}

export async function fetchIngestionSourceStatus(name: string): Promise<IngestionSourceStatus> {
  const r = await fetchWithAuth(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}/status`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to fetch source status: ${r.status}`)
  return r.json()
}

export interface UploadResponse {
  filename: string
  server_path: string
  size_bytes: number
  uploaded_at: string
  suggested_source_type: string
}

export async function uploadMailboxFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    // Track upload progress
    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100)
          onProgress(percent)
        }
      })
    }

    xhr.addEventListener('load', () => {
      if (xhr.status === 201) {
        try {
          const response = JSON.parse(xhr.responseText)
          resolve(response)
        } catch (e) {
          reject(new Error('Failed to parse upload response'))
        }
      } else if (xhr.status === 401) {
        // Handle unauthorized - callback to redirect to login
        const callback = getUnauthorizedCallback()
        if (callback) callback()
        reject(new Error('UNAUTHORIZED'))
      } else {
        try {
          const error = JSON.parse(xhr.responseText)
          reject(new Error(error.detail || `Upload failed: ${xhr.status}`))
        } catch (e) {
          reject(new Error(`Upload failed: ${xhr.status}`))
        }
      }
    })

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed: Network error'))
    })

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload cancelled'))
    })

    xhr.open('POST', `${INGESTION_API_BASE}/api/uploads`)
    // Enable cookie-based authentication
    xhr.withCredentials = true
    console.log('[uploadMailboxFile] Using cookie-based authentication')
    xhr.send(formData)
  })
}

// Admin Role Management API

export interface PendingRoleAssignment {
  user_id: string
  requested_roles: string[]
  requested_at: string
  status: string
  user_email?: string
  user_name?: string
}

function normalizePendingRoleAssignment(input: unknown): PendingRoleAssignment | null {
  if (!input || typeof input !== 'object') return null

  const record = input as Record<string, unknown>
  const userId = record.user_id
  if (typeof userId !== 'string' || userId.length === 0) return null

  const asStringArray = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && v.length > 0) : []

  const requestedRolesFromRequested = asStringArray(record.requested_roles)
  const requestedRolesFromRoles = asStringArray(record.roles)
  const requestedRoles =
    requestedRolesFromRequested.length > 0
      ? requestedRolesFromRequested
      : requestedRolesFromRoles.length > 0
        ? requestedRolesFromRoles
        : typeof record.requested_role === 'string' && record.requested_role.length > 0
          ? [record.requested_role]
          : typeof record.role === 'string' && record.role.length > 0
            ? [record.role]
            : []

  // If an assignment has no requested roles, it's not actionable and should not be shown.
  if (requestedRoles.length === 0) return null

  const requestedAt =
    typeof record.requested_at === 'string'
      ? record.requested_at
      : typeof record.updated_at === 'string'
        ? record.updated_at
        : new Date().toISOString()

  const status = typeof record.status === 'string' && record.status.length > 0 ? record.status : 'pending'

  const userEmail =
    typeof record.user_email === 'string'
      ? record.user_email
      : typeof record.email === 'string'
        ? record.email
        : undefined

  const userName =
    typeof record.user_name === 'string'
      ? record.user_name
      : typeof record.name === 'string'
        ? record.name
        : undefined

  return {
    user_id: userId,
    requested_roles: requestedRoles,
    requested_at: requestedAt,
    status,
    user_email: userEmail,
    user_name: userName,
  }
}

export interface UserRoleRecord {
  user_id: string
  email?: string
  name?: string
  roles: string[]
  status: string
  created_at?: string
  updated_at?: string
}

export interface PendingAssignmentsResponse {
  assignments: PendingRoleAssignment[]
  total: number
  limit: number
  skip: number
}

const AUTH_API_BASE = '/auth'

export async function fetchPendingRoleAssignments(
  params: {
    user_id?: string
    role?: string
    limit?: number
    skip?: number
    sort_by?: string
    sort_order?: number
  } = {}
): Promise<PendingAssignmentsResponse> {
  const queryParams = toQuery({
    user_id: params.user_id,
    role: params.role,
    limit: params.limit ?? 50,
    skip: params.skip ?? 0,
    sort_by: params.sort_by ?? 'requested_at',
    sort_order: params.sort_order ?? -1,
  })
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/role-assignments/pending?${queryParams}`)
  if (!r.ok) throw new Error(`Failed to fetch pending assignments: ${r.status}`)

  const json = await r.json()

  // The admin endpoint has evolved over time. Some deployments return a simple
  // array of assignments; others return a paginated object.
  if (Array.isArray(json)) {
    const normalizedAssignments = (json as unknown[])
      .map(normalizePendingRoleAssignment)
      .filter(
        (assignment: PendingRoleAssignment | null): assignment is PendingRoleAssignment =>
          assignment !== null
      )
    return {
      assignments: normalizedAssignments,
      total: normalizedAssignments.length,
      limit: params.limit ?? 50,
      skip: params.skip ?? 0,
    }
  }

  const assignments = Array.isArray(json?.assignments) ? json.assignments : []
  const total = typeof json?.total === 'number' ? json.total : assignments.length
  const limit = typeof json?.limit === 'number' ? json.limit : params.limit ?? 50
  const skip = typeof json?.skip === 'number' ? json.skip : params.skip ?? 0

  const normalizedAssignments = assignments
    .map(normalizePendingRoleAssignment)
    .filter(
      (assignment: PendingRoleAssignment | null): assignment is PendingRoleAssignment =>
        assignment !== null
    )

  return { assignments: normalizedAssignments, total, limit, skip }
}

export async function fetchUserRoles(userId: string): Promise<UserRoleRecord> {
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/users/${encodeURIComponent(userId)}/roles`)
  if (r.status === 404) throw new Error('User not found')
  if (!r.ok) throw new Error(`Failed to fetch user roles: ${r.status}`)
  return r.json()
}

export interface UserSearchResponse {
  users: UserRoleRecord[]
  count: number
  search_by: string
  search_term: string
}

export async function searchUsers(
  searchTerm: string,
  searchBy: 'user_id' | 'email' | 'name' = 'email'
): Promise<UserSearchResponse> {
  const params = toQuery({ search_term: searchTerm, search_by: searchBy })
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/users/search?${params}`)
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to search users: ${r.status}`))
  }
  return r.json()
}

export async function assignUserRoles(userId: string, roles: string[]): Promise<UserRoleRecord> {
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/users/${encodeURIComponent(userId)}/roles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roles }),
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to assign roles: ${r.status}`))
  }
  return r.json()
}

export async function revokeUserRoles(userId: string, roles: string[]): Promise<UserRoleRecord> {
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/users/${encodeURIComponent(userId)}/roles`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roles }),
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to revoke roles: ${r.status}`))
  }
  return r.json()
}

export async function denyRoleAssignment(userId: string): Promise<UserRoleRecord> {
  const r = await fetchWithAuth(`${AUTH_API_BASE}/admin/users/${encodeURIComponent(userId)}/deny`, {
    method: 'POST',
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(formatErrorMessage(error, `Failed to deny role assignment: ${r.status}`))
  }
  return r.json()
}
