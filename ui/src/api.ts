// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

export interface Report {
  _id: string
  thread_id: string
  generated_at: string
  generated_by?: string
  content_markdown: string
  citations: Array<{ message_id: string; chunk_id: string; quote?: string | null }>
  archive_metadata?: { source?: string | null } | null
  thread_metadata?: {
    participant_count?: number
    message_count?: number
    subject?: string
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
  summary_id?: string
}

export interface Message {
  _id: string
  message_id: string
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
  chunk_id: string
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

// If VITE_REPORTING_API_URL is not set, use same-origin and rely on Nginx proxy (/api -> reporting)
const DEFAULT_API = ''
const base = import.meta.env.VITE_REPORTING_API_URL || DEFAULT_API

export function reportingApiBase(): string {
  return base
}

export async function fetchSources(): Promise<string[]> {
  const r = await fetch(`${base}/api/sources`)
  if (!r.ok) throw new Error(`Sources fetch failed: ${r.status}`)
  const data = await r.json()
  return data.sources ?? []
}

export interface ReportsQuery {
  thread_id?: string
  topic?: string
  start_date?: string
  end_date?: string
  source?: string
  min_participants?: string
  max_participants?: string
  min_messages?: string
  max_messages?: string
  limit?: number
  skip?: number
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
  if (q.start_date) params.start_date = q.start_date
  if (q.end_date) params.end_date = q.end_date
  if (q.source) params.source = q.source
  if (q.min_participants) params.min_participants = q.min_participants
  if (q.max_participants) params.max_participants = q.max_participants
  if (q.min_messages) params.min_messages = q.min_messages
  if (q.max_messages) params.max_messages = q.max_messages

  const url = `${base}/api/reports?${toQuery(params)}`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`Reports fetch failed: ${r.status}`)
  return r.json()
}

export async function searchReportsByTopic(topic: string, limit = 20): Promise<Report[]> {
  const params = toQuery({ topic, limit, min_score: 0.5 })
  const r = await fetch(`${base}/api/reports/search?${params}`)
  if (!r.ok) throw new Error(`Topic search failed: ${r.status}`)
  const data = await r.json()
  return data.reports ?? []
}

export async function fetchReport(id: string): Promise<Report> {
  const r = await fetch(`${base}/api/reports/${id}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Report fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThreadSummary(threadId: string): Promise<Report> {
  const r = await fetch(`${base}/api/threads/${threadId}/summary`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Thread summary fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThread(threadId: string): Promise<Thread> {
  const r = await fetch(`${base}/api/threads/${threadId}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Thread fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchThreadMessages(
  threadId: string,
  limit = 100,
  skip = 0
): Promise<{ messages: Message[]; count: number }> {
  const params = toQuery({ thread_id: threadId, limit, skip })
  const r = await fetch(`${base}/api/messages?${params}`)
  if (!r.ok) throw new Error(`Messages fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchMessage(messageDocId: string): Promise<Message> {
  const r = await fetch(`${base}/api/messages/${messageDocId}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Message fetch failed: ${r.status}`)
  return r.json()
}

export async function fetchMessageChunks(
  messageId: string,
  limit = 100
): Promise<{ chunks: Chunk[]; count: number }> {
  const params = toQuery({ message_id: messageId, limit })
  const r = await fetch(`${base}/api/chunks?${params}`)
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
  const r = await fetch(`${INGESTION_API_BASE}/api/sources${params}`)
  if (!r.ok) throw new Error(`Failed to fetch sources: ${r.status}`)
  return r.json()
}

export async function fetchIngestionSource(name: string): Promise<IngestionSource> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to fetch source: ${r.status}`)
  return r.json()
}

export async function createIngestionSource(source: IngestionSource): Promise<{ message: string; source: IngestionSource }> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source),
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(error.detail || `Failed to create source: ${r.status}`)
  }
  return r.json()
}

export async function updateIngestionSource(name: string, source: IngestionSource): Promise<{ message: string; source: IngestionSource }> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source),
  })
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(error.detail || `Failed to update source: ${r.status}`)
  }
  return r.json()
}

export async function deleteIngestionSource(name: string): Promise<{ message: string }> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to delete source: ${r.status}`)
  return r.json()
}

export async function triggerIngestionSource(name: string): Promise<{ source_name: string; status: string; message: string; triggered_at: string }> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}/trigger`, {
    method: 'POST',
  })
  if (!r.ok) {
    const error = await r.json().catch(() => ({ detail: `Request failed: ${r.status}` }))
    throw new Error(error.detail || `Failed to trigger ingestion: ${r.status}`)
  }
  return r.json()
}

export async function fetchIngestionSourceStatus(name: string): Promise<IngestionSourceStatus> {
  const r = await fetch(`${INGESTION_API_BASE}/api/sources/${encodeURIComponent(name)}/status`)
  if (r.status === 404) throw new Error('NOT_FOUND')
  if (!r.ok) throw new Error(`Failed to fetch source status: ${r.status}`)
  return r.json()
}
