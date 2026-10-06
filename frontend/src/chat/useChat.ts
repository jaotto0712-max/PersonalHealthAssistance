import { useCallback, useEffect, useReducer, useRef } from 'react'

import type { ApiClient } from '../api/types'
import { type ChatMessage, chatReducer, initialChatState, toHistory } from './chatState'
import { createTokenBatcher } from './tokenBatcher'

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError'

type Options = {
  /** Returns the conversation to save into, creating one on the first message of a new chat. */
  ensureConversation?: () => Promise<string | null>
  /** Called after each exchange settles (e.g. to refresh the conversation list). */
  onSettled?: () => void
}

export function useChat(client: ApiClient, onError: (message: string) => void, options: Options = {}) {
  const { ensureConversation, onSettled } = options
  const [state, dispatch] = useReducer(chatReducer, initialChatState)
  const stateRef = useRef(state)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    stateRef.current = state
  }, [state])
  useEffect(() => () => abortRef.current?.abort(), [])

  const send = useCallback(
    async (text: string) => {
      const message = text.trim()
      if (!message || abortRef.current) return
      const history = toHistory(stateRef.current.messages)
      const id = crypto.randomUUID()
      dispatch({ type: 'send', userId: crypto.randomUUID(), assistantId: id, text: message })

      const controller = new AbortController()
      abortRef.current = controller
      let conversationId: string | null = null
      try {
        conversationId = (await ensureConversation?.()) ?? null
      } catch (e) {
        onError(`Could not save this chat: ${e instanceof Error ? e.message : e}`)
      }
      const batcher = createTokenBatcher((t) => dispatch({ type: 'tokens', id, text: t }))
      let finished = false
      try {
        const request = { message, history, ...(conversationId ? { conversation_id: conversationId } : {}) }
        for await (const event of client.chat(request, controller.signal)) {
          switch (event.type) {
            case 'meta':
              if (event.data.emergency) dispatch({ type: 'emergency', id, category: event.data.category })
              break
            case 'token':
              batcher.push(event.data.text)
              break
            case 'sources':
              batcher.flush()
              dispatch({ type: 'sources', id, items: event.data.items })
              break
            case 'done':
              batcher.flush()
              dispatch({ type: 'finish', id, status: 'done' })
              finished = true
              break
            case 'error':
              batcher.flush()
              dispatch({ type: 'finish', id, status: 'error', error: event.data.message })
              onError(event.data.message)
              finished = true
              break
          }
        }
        batcher.flush()
        if (!finished) dispatch({ type: 'finish', id, status: 'done' })
      } catch (e) {
        batcher.flush()
        if (isAbort(e)) {
          dispatch({ type: 'finish', id, status: 'stopped' })
        } else {
          const msg = e instanceof Error ? e.message : 'Something went wrong.'
          dispatch({ type: 'finish', id, status: 'error', error: msg })
          onError(msg)
        }
      } finally {
        abortRef.current = null
        onSettled?.()
      }
    },
    [client, onError, ensureConversation, onSettled],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    dispatch({ type: 'reset' })
  }, [])

  const load = useCallback((messages: ChatMessage[]) => {
    abortRef.current?.abort()
    dispatch({ type: 'load', messages })
  }, [])

  return { messages: state.messages, isStreaming: state.streamingId !== null, send, stop, reset, load }
}
