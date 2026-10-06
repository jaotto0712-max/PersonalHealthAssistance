import type {
  ApiClient,
  ChatEvent,
  ConversationDetail,
  ConversationSummary,
  DocumentRecord,
  Health,
} from '../api/types'

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

export function conversation(partial: Partial<ConversationDetail> = {}): ConversationDetail {
  const messages = partial.messages ?? []
  return {
    id: crypto.randomUUID(),
    title: 'Saved chat',
    created_at: '2026-10-06T10:00:00Z',
    updated_at: '2026-10-06T10:00:00Z',
    message_count: messages.length,
    messages,
    ...partial,
  }
}

type Overrides = Partial<ApiClient> & {
  healthValue?: Health
  docs?: DocumentRecord[]
  conversations?: ConversationDetail[]
}

export function fakeClient(overrides: Overrides = {}): ApiClient {
  const {
    healthValue = { status: 'ok', version: 'test', llm: 'ok', model: 'phi3-medquad-v2' },
    docs = [],
    conversations = [],
    ...rest
  } = overrides
  const store = new Map(conversations.map((c) => [c.id, c]))
  const summary = ({ messages, ...c }: ConversationDetail): ConversationSummary => ({ ...c, message_count: messages.length })
  return {
    health: async () => healthValue,
    listConversations: async () => [...store.values()].map(summary),
    createConversation: async () => {
      const c = conversation({ title: null })
      store.set(c.id, c)
      return summary(c)
    },
    getConversation: async (id) => {
      const c = store.get(id)
      if (!c) throw new Error('Conversation not found.')
      return c
    },
    renameConversation: async (id, title) => {
      const c = { ...store.get(id)!, title }
      store.set(id, c)
      return summary(c)
    },
    deleteConversation: async (id) => {
      store.delete(id)
    },
    deleteAllConversations: async () => store.clear(),
    listDocuments: async () => docs,
    uploadDocument: async (file) => doc({ filename: file.name, size_bytes: file.size }),
    deleteDocument: async () => {},
    clearDocuments: async () => {},
    chat: controlledChat().chat,
    ...rest,
  }
}
