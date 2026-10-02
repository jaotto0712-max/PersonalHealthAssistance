import { describe, expect, it } from 'vitest'

import { parseSSE, toChatEvents } from './sse'

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c))
      controller.close()
    },
  })
}

async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = []
  for await (const x of it) out.push(x)
  return out
}

describe('parseSSE', () => {
  it('parses events split across arbitrary chunks', async () => {
    const msgs = await collect(parseSSE(streamOf('event: tok', 'en\ndata: {"text":"Hi"}\n', '\nevent: done\ndata: {}\n\n')))
    expect(msgs).toEqual([
      { event: 'token', data: '{"text":"Hi"}' },
      { event: 'done', data: '{}' },
    ])
  })

  it('handles CRLF line endings even when CR and LF land in different chunks', async () => {
    const msgs = await collect(parseSSE(streamOf('event: meta\r\ndata: {"a":1}\r', '\n\r\n: keep-alive\r\n\r\n')))
    expect(msgs).toEqual([{ event: 'meta', data: '{"a":1}' }])
  })

  it('joins multi-line data and flushes a final event without trailing blank line', async () => {
    const msgs = await collect(parseSSE(streamOf('data: line1\ndata: line2')))
    expect(msgs).toEqual([{ event: 'message', data: 'line1\nline2' }])
  })
})

describe('toChatEvents', () => {
  it('maps meta/token/sources/done/error and skips unknown events', async () => {
    const body = [
      'event: meta\ndata: {"emergency":false,"retrieved_count":1}\n\n',
      'event: token\ndata: {"text":"Hello "}\n\n',
      'event: ping\ndata: {}\n\n',
      'event: sources\ndata: {"items":[]}\n\n',
      'event: error\ndata: {"code":"llm_unavailable","message":"Start Ollama"}\n\n',
      'event: done\ndata: {"disclaimer":"Not medical advice"}\n\n',
    ]
    const events = await collect(toChatEvents(parseSSE(streamOf(...body))))
    expect(events.map((e) => e.type)).toEqual(['meta', 'token', 'sources', 'error', 'done'])
    expect(events[1]).toEqual({ type: 'token', data: { text: 'Hello ' } })
    expect(events[3]).toEqual({ type: 'error', data: { code: 'llm_unavailable', message: 'Start Ollama' } })
  })
})
