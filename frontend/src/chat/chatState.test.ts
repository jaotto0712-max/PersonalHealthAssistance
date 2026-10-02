import { describe, expect, it } from 'vitest'

import { type ChatMessage, chatReducer, initialChatState, toHistory } from './chatState'

describe('chatReducer', () => {
  it('streams tokens into the assistant message and finishes', () => {
    let s = chatReducer(initialChatState, { type: 'send', userId: 'u', assistantId: 'a', text: 'Hi' })
    expect(s.streamingId).toBe('a')
    s = chatReducer(s, { type: 'tokens', id: 'a', text: 'Hel' })
    s = chatReducer(s, { type: 'tokens', id: 'a', text: 'lo' })
    s = chatReducer(s, { type: 'finish', id: 'a', status: 'done' })
    expect(s.streamingId).toBeNull()
    expect(s.messages[1]).toMatchObject({ content: 'Hello', status: 'done' })
  })

  it('does not overwrite a finished status (stop after done)', () => {
    let s = chatReducer(initialChatState, { type: 'send', userId: 'u', assistantId: 'a', text: 'Hi' })
    s = chatReducer(s, { type: 'finish', id: 'a', status: 'done' })
    s = chatReducer(s, { type: 'finish', id: 'a', status: 'stopped' })
    expect(s.messages[1].status).toBe('done')
  })
})

describe('toHistory', () => {
  const msg = (p: Partial<ChatMessage>): ChatMessage => ({ id: crypto.randomUUID(), role: 'user', content: 'x', status: 'done', ...p })

  it('keeps completed and stopped turns, drops streaming, emergency, errors, and empties', () => {
    const history = toHistory([
      msg({ content: 'q1' }),
      msg({ role: 'assistant', content: 'a1' }),
      msg({ content: 'q2' }),
      msg({ role: 'assistant', content: 'partial', status: 'stopped' }),
      msg({ content: 'chest pain' }),
      msg({ role: 'assistant', content: 'Call 911', emergency: { category: 'cardiac' } }),
      msg({ role: 'assistant', content: '', status: 'error' }),
      msg({ role: 'assistant', content: 'oops', status: 'error' }),
      msg({ role: 'assistant', content: '...', status: 'streaming' }),
    ])
    expect(history.map((t) => t.content)).toEqual(['q1', 'a1', 'q2', 'partial', 'chest pain'])
  })

  it('caps history to the 20 most recent turns', () => {
    const many = Array.from({ length: 30 }, (_, i) => msg({ content: `m${i}` }))
    const history = toHistory(many)
    expect(history).toHaveLength(20)
    expect(history[0].content).toBe('m10')
  })
})
