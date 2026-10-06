// In-memory stand-in for the backend so the UI can be developed and demoed before the
// RAG and chat changes land. Enabled with VITE_MOCK_API=true (`npm run dev:mock`).
import {
  type ApiClient,
  ApiError,
  type ChatEvent,
  type ConversationDetail,
  type DocumentRecord,
  type Source,
  precheckUpload,
} from './types'

const DISCLAIMER =
  'General health information only — not a substitute for professional medical advice. In an emergency, call 911.'

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'))
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

const EMERGENCIES: { pattern: RegExp; category: string }[] = [
  { pattern: /\b(end|take) my (own )?life\b|\bkill myself\b|\bsuicid|\bself[- ]?harm/i, category: 'self_harm' },
  { pattern: /\bchest (pain|pressure|tightness)\b/i, category: 'cardiac' },
  { pattern: /\b(can'?t|cannot|trouble) breath/i, category: 'breathing' },
  { pattern: /\boverdos|\bpoison/i, category: 'overdose' },
]

const EMERGENCY_TEXT: Record<string, string> = {
  self_harm:
    "You don't have to go through this alone. Please call or text **988** (Suicide & Crisis Lifeline) now to talk with someone, any time of day. If you are in immediate danger, call **911**.",
  default:
    'What you describe could be a medical emergency. **Call 911** or go to the nearest emergency room now — please do not wait for an online answer.',
}

function detectEmergency(message: string): string | null {
  if (/\b(no|denies|without)\s+chest/i.test(message)) return null
  return EMERGENCIES.find((e) => e.pattern.test(message))?.category ?? null
}

function groundedAnswer(docs: DocumentRecord[]): { text: string; sources: Source[] } {
  const [first, second = first] = docs
  const sources: Source[] = [
    { n: 1, doc_id: first.id, filename: first.filename, page: 2, score: 0.82, cited: true, snippet: 'LDL Cholesterol ........ 162 mg/dL   (ref < 100)   HIGH' },
    { n: 2, doc_id: first.id, filename: first.filename, page: 2, score: 0.74, cited: true, snippet: 'HDL Cholesterol ........ 48 mg/dL    (ref > 40)' },
    { n: 3, doc_id: second.id, filename: second.filename, page: 1, score: 0.51, cited: false, snippet: 'Plan: recheck lipid panel in 3 months; discussed diet and exercise.' },
  ]
  const text =
    'Your LDL ("bad") cholesterol was **162 mg/dL** [1], which is above the reference range of under 100 mg/dL listed on your report. ' +
    'Your HDL ("good") cholesterol was **48 mg/dL** [2], within its normal range.\n\n' +
    'Elevated LDL is common and is usually managed with diet, physical activity, and sometimes medication. ' +
    'Your clinician is the best person to explain what these numbers mean for you.\n\n' +
    '_Mock API response — start the backend for real answers._'
  return { text, sources }
}

const GENERAL_ANSWER =
  "I couldn't find anything about this in your uploaded documents, so here is general information.\n\n" +
  'Most health questions depend on your personal history, so use this as a starting point for a conversation with your clinician. ' +
  'Upload a lab report or visit summary to get answers grounded in your own records.\n\n' +
  '_Mock API response — start the backend for real answers._'

export function createMockClient(options: { tokenDelayMs?: number } = {}): ApiClient {
  const tokenDelay = options.tokenDelayMs ?? 35
  let docs: DocumentRecord[] = []
  const conversations = new Map<string, ConversationDetail>()
  const now = () => new Date().toISOString()
  const summary = ({ messages, ...c }: ConversationDetail) => ({ ...c, message_count: messages.length })
  const conv = (id: string) => {
    const c = conversations.get(id)
    if (!c) throw new ApiError(404, 'Conversation not found.')
    return c
  }

  const client: ApiClient = {
    async health() {
      return { status: 'ok', version: 'mock', llm: 'ok', model: 'mock' }
    },

    async listDocuments() {
      return [...docs]
    },

    async uploadDocument(file, onProgress) {
      const reason = precheckUpload(file)
      if (reason) throw new ApiError(/larger/.test(reason) ? 413 : 415, reason)
      for (let step = 1; step <= 5; step++) {
        await sleep(120)
        onProgress?.(step / 5)
      }
      const existing = docs.find((d) => d.filename === file.name && d.size_bytes === file.size)
      if (existing) return existing
      const needsOcr = /scan/i.test(file.name)
      const record: DocumentRecord = {
        id: crypto.randomUUID(),
        filename: file.name,
        size_bytes: file.size,
        pages: Math.max(1, Math.round(file.size / 60_000)),
        chunks: needsOcr ? 0 : Math.max(1, Math.round(file.size / 800)),
        status: needsOcr ? 'needs_ocr' : 'indexed',
        uploaded_at: new Date().toISOString(),
      }
      docs = [...docs, record]
      return record
    },

    async deleteDocument(id) {
      await sleep(150)
      if (!docs.some((d) => d.id === id)) throw new ApiError(404, 'Document not found.')
      docs = docs.filter((d) => d.id !== id)
    },

    async clearDocuments() {
      await sleep(150)
      docs = []
    },

    async listConversations() {
      return [...conversations.values()].map(summary).sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    },

    async createConversation() {
      const c: ConversationDetail = { id: crypto.randomUUID(), title: null, created_at: now(), updated_at: now(), message_count: 0, messages: [] }
      conversations.set(c.id, c)
      return summary(c)
    },

    async getConversation(id) {
      const c = conv(id)
      return { ...c, message_count: c.messages.length }
    },

    async renameConversation(id, title) {
      const c = conv(id)
      c.title = title
      c.updated_at = now()
      return summary(c)
    },

    async deleteConversation(id) {
      conv(id)
      conversations.delete(id)
    },

    async deleteAllConversations() {
      conversations.clear()
    },

    async *chat(req, signal): AsyncGenerator<ChatEvent> {
      const saved = req.conversation_id ? conv(req.conversation_id) : null
      if (saved) {
        saved.title ??= req.message.slice(0, 60)
        saved.messages.push({ id: crypto.randomUUID(), role: 'user', content: req.message, status: 'done', sources: [], emergency: null, error: null, created_at: now() })
        saved.updated_at = now()
      }
      let answer = ''
      let status: 'done' | 'stopped' = 'stopped'
      let savedSources: Source[] = []
      let emergencyCategory: string | null = null
      try {
        for await (const event of mockAnswer(req, signal)) {
          if (event.type === 'token') answer += event.data.text
          if (event.type === 'sources') savedSources = event.data.items
          if (event.type === 'meta' && event.data.emergency) emergencyCategory = event.data.category ?? 'emergency'
          if (event.type === 'done') status = 'done'
          yield event
        }
      } finally {
        saved?.messages.push({ id: crypto.randomUUID(), role: 'assistant', content: answer, status, sources: savedSources, emergency: emergencyCategory, error: null, created_at: now() })
      }
    },
  }

  return client

  async function* mockAnswer(req: { message: string }, signal: AbortSignal): AsyncGenerator<ChatEvent> {
      await sleep(300, signal)
      const category = detectEmergency(req.message)
      const indexed = docs.filter((d) => d.status === 'indexed')
      const { text, sources } = category
        ? { text: EMERGENCY_TEXT[category] ?? EMERGENCY_TEXT.default, sources: [] }
        : indexed.length
          ? groundedAnswer(indexed)
          : { text: GENERAL_ANSWER, sources: [] }

      yield {
        type: 'meta',
        data: { emergency: category !== null, category: category ?? undefined, retrieved_count: sources.length, model: 'mock' },
      }
      for (const piece of text.match(/\S+\s*/g) ?? []) {
        await sleep(category ? 5 : tokenDelay, signal)
        yield { type: 'token', data: { text: piece } }
      }
      yield { type: 'sources', data: { items: sources } }
      yield { type: 'done', data: { disclaimer: DISCLAIMER } }
  }
}
