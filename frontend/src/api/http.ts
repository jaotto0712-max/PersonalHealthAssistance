import { parseSSE, toChatEvents } from './sse'
import {
  type ApiClient,
  ApiError,
  type ChatEvent,
  type ChatRequest,
  type DocumentRecord,
  type Health,
  uploadErrorReason,
} from './types'

async function errorFrom(res: Response): Promise<ApiError> {
  let detail: string | undefined
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') detail = body.detail
  } catch {
    // non-JSON error body
  }
  return new ApiError(res.status, detail ?? (res.statusText || `HTTP ${res.status}`))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) throw await errorFrom(res)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const httpClient: ApiClient = {
  health: () => request<Health>('/api/health'),

  listDocuments: () => request<DocumentRecord[]>('/api/documents'),

  // XMLHttpRequest instead of fetch: fetch cannot report upload progress.
  uploadDocument(file, onProgress) {
    return new Promise<DocumentRecord>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/documents')
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress?.(e.loaded / e.total)
      }
      xhr.onload = () => {
        let body: unknown = null
        try {
          body = JSON.parse(xhr.responseText)
        } catch {
          // non-JSON body
        }
        if (xhr.status >= 200 && xhr.status < 300) return resolve(body as DocumentRecord)
        const detail = (body as { detail?: unknown } | null)?.detail
        reject(new ApiError(xhr.status, uploadErrorReason(xhr.status, typeof detail === 'string' ? detail : undefined)))
      }
      xhr.onerror = () => reject(new ApiError(0, uploadErrorReason(0)))
      const form = new FormData()
      form.append('file', file)
      xhr.send(form)
    })
  },

  deleteDocument: (id) => request<void>(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  clearDocuments: () => request<void>('/api/documents', { method: 'DELETE' }),

  async *chat(req: ChatRequest, signal: AbortSignal): AsyncGenerator<ChatEvent> {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(req),
      signal,
    })
    if (!res.ok || !res.body) throw await errorFrom(res)
    yield* toChatEvents(parseSSE(res.body))
  },
}
