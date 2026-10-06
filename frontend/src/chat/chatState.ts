import { type ChatTurn, MAX_HISTORY_TURNS, type Source, type StoredMessage } from '../api/types'

export type MessageStatus = 'streaming' | 'done' | 'stopped' | 'error'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: MessageStatus
  sources?: Source[]
  emergency?: { category?: string }
  error?: string
}

export interface ChatState {
  messages: ChatMessage[]
  streamingId: string | null
}

export type ChatAction =
  | { type: 'send'; userId: string; assistantId: string; text: string }
  | { type: 'emergency'; id: string; category?: string }
  | { type: 'tokens'; id: string; text: string }
  | { type: 'sources'; id: string; items: Source[] }
  | { type: 'finish'; id: string; status: Exclude<MessageStatus, 'streaming'>; error?: string }
  | { type: 'reset' }
  | { type: 'load'; messages: ChatMessage[] }

export const initialChatState: ChatState = { messages: [], streamingId: null }

function update(state: ChatState, id: string, patch: (m: ChatMessage) => ChatMessage): ChatState {
  return { ...state, messages: state.messages.map((m) => (m.id === id ? patch(m) : m)) }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'send':
      return {
        streamingId: action.assistantId,
        messages: [
          ...state.messages,
          { id: action.userId, role: 'user', content: action.text, status: 'done' },
          { id: action.assistantId, role: 'assistant', content: '', status: 'streaming' },
        ],
      }
    case 'emergency':
      return update(state, action.id, (m) => ({ ...m, emergency: { category: action.category } }))
    case 'tokens':
      return update(state, action.id, (m) => ({ ...m, content: m.content + action.text }))
    case 'sources':
      return update(state, action.id, (m) => ({ ...m, sources: action.items }))
    case 'finish': {
      const next = update(state, action.id, (m) =>
        m.status === 'streaming' ? { ...m, status: action.status, error: action.error } : m,
      )
      return { ...next, streamingId: state.streamingId === action.id ? null : state.streamingId }
    }
    case 'reset':
      return initialChatState
    case 'load':
      return { messages: action.messages, streamingId: null }
  }
}

/**
 * Conversation history sent with the next request: completed turns only, excluding
 * emergency alerts and failed/empty replies, capped to the most recent turns.
 */
export function toHistory(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter((m) => m.status !== 'streaming' && !m.emergency && m.content.trim() !== '')
    .filter((m) => !(m.role === 'assistant' && m.status === 'error'))
    .map((m) => ({ role: m.role, content: m.content }))
    .slice(-MAX_HISTORY_TURNS)
}

/** A saved message from the conversation store, as the chat thread renders it. */
export function fromStored(m: StoredMessage): ChatMessage {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    status: m.status,
    sources: m.sources.length ? m.sources : undefined,
    emergency: m.emergency ? { category: m.emergency } : undefined,
    error: m.error ?? undefined,
  }
}
