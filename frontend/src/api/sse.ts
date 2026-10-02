import type { ChatEvent } from './types'

export interface SSEMessage {
  event: string
  data: string
}

function parseBlock(block: string): SSEMessage | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length ? { event, data: data.join('\n') } : null
}

/** Parse a Server-Sent Events byte stream (LF or CRLF line endings, arbitrary chunking). */
export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<SSEMessage> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      // Normalize CRLF/CR to LF, holding back a trailing CR that may pair with the next chunk.
      const heldCR = !done && buffer.endsWith('\r')
      buffer = (heldCR ? buffer.slice(0, -1) : buffer).replace(/\r\n?/g, '\n') + (heldCR ? '\r' : '')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const message = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (message) yield message
      }
      if (done) break
    }
    const tail = parseBlock(buffer)
    if (tail) yield tail
  } finally {
    reader.releaseLock()
  }
}

const CHAT_EVENT_TYPES = new Set(['meta', 'token', 'sources', 'done', 'error'])

/** Map raw SSE messages to typed chat events, skipping unknown event names. */
export async function* toChatEvents(messages: AsyncIterable<SSEMessage>): AsyncGenerator<ChatEvent> {
  for await (const { event, data } of messages) {
    if (CHAT_EVENT_TYPES.has(event)) yield { type: event, data: JSON.parse(data) } as ChatEvent
  }
}
