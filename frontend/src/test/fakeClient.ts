import type { ApiClient, ChatEvent, DocumentRecord, Health } from '../api/types'

/** A chat stream the test drives event by event; aborting the request rejects like fetch does. */
export function controlledChat() {
  const queue: (ChatEvent | 'end')[] = []
  let wake: (() => void) | null = null
  const notify = () => {
    wake?.()
    wake = null
  }

  async function* chat(_req: unknown, signal: AbortSignal): AsyncGenerator<ChatEvent> {
    for (;;) {
      while (queue.length === 0) {
        await new Promise<void>((resolve, reject) => {
          wake = resolve
          signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
        })
      }
      const next = queue.shift()!
      if (next === 'end') return
      yield next
    }
  }

  return {
    chat: chat as ApiClient['chat'],
    push(...events: ChatEvent[]) {
      queue.push(...events)
      notify()
    },
    end() {
      queue.push('end')
      notify()
    },
  }
}

export function doc(partial: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: crypto.randomUUID(),
    filename: 'labs.pdf',
    size_bytes: 120_000,
    pages: 3,
    chunks: 12,
    status: 'indexed',
    uploaded_at: '2026-10-01T12:00:00Z',
    ...partial,
  }
}

export function fakeClient(overrides: Partial<ApiClient> & { healthValue?: Health; docs?: DocumentRecord[] } = {}): ApiClient {
  const { healthValue = { status: 'ok', version: 'test', llm: 'ok', model: 'phi3-medquad' }, docs = [], ...rest } = overrides
  return {
    health: async () => healthValue,
    listDocuments: async () => docs,
    uploadDocument: async (file) => doc({ filename: file.name, size_bytes: file.size }),
    deleteDocument: async () => {},
    clearDocuments: async () => {},
    chat: controlledChat().chat,
    ...rest,
  }
}
