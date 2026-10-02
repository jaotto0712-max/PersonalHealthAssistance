// Contracts shared with the backend. Documents: add-local-document-rag; chat/health:
// add-rag-chat-orchestration (see openspec/changes/*/specs).

export type LlmStatus = 'ok' | 'unavailable' | 'model_missing'

export interface Health {
  status: string
  version: string
  llm?: LlmStatus
  model?: string
  hint?: string
}

export type DocumentStatus = 'indexed' | 'needs_ocr'

export interface DocumentRecord {
  id: string
  filename: string
  size_bytes: number
  pages: number
  chunks: number
  status: DocumentStatus
  uploaded_at: string
}

export interface Source {
  n: number
  doc_id: string
  filename: string
  page: number
  score: number
  snippet: string
  cited: boolean
}

export interface ChatMeta {
  emergency: boolean
  category?: string
  retrieved_count?: number
  model?: string
}

export type ChatEvent =
  | { type: 'meta'; data: ChatMeta }
  | { type: 'token'; data: { text: string } }
  | { type: 'sources'; data: { items: Source[] } }
  | { type: 'done'; data: { disclaimer: string; usage?: Record<string, number> } }
  | { type: 'error'; data: { code: string; message: string } }

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  history: ChatTurn[]
}

export interface ApiClient {
  health(): Promise<Health>
  listDocuments(): Promise<DocumentRecord[]>
  uploadDocument(file: File, onProgress?: (fraction: number) => void): Promise<DocumentRecord>
  deleteDocument(id: string): Promise<void>
  clearDocuments(): Promise<void>
  chat(request: ChatRequest, signal: AbortSignal): AsyncIterable<ChatEvent>
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.docx'] as const
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024
export const MAX_MESSAGE_CHARS = 4000
export const MAX_HISTORY_TURNS = 20

/** Human-readable reason for a rejected upload, preferring the server's own message. */
export function uploadErrorReason(status: number, detail?: string): string {
  if (detail) return detail
  if (status === 413) return 'File is larger than the 20 MB limit.'
  if (status === 415) return 'Unsupported file type. Use PDF, TXT, MD, or DOCX.'
  if (status === 0) return 'Could not reach the backend. Is it running?'
  return `Upload failed (HTTP ${status}).`
}

/** Client-side pre-check mirroring the server's limits; returns a reason or null if OK. */
export function precheckUpload(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) return uploadErrorReason(415)
  if (file.size > MAX_UPLOAD_BYTES) return uploadErrorReason(413)
  return null
}
