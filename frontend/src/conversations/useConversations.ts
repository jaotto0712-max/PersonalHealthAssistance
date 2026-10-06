import { useCallback, useEffect, useRef, useState } from 'react'

import type { ApiClient, ConversationDetail, ConversationSummary } from '../api/types'

const HASH = /^#c=([\w-]+)$/

function readHash(): string | null {
  return window.location.hash.match(HASH)?.[1] ?? null
}

/** Saved conversations (stored by the local backend) and which one is open. */
export function useConversations(client: ApiClient, onError: (message: string) => void) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(readHash)
  const activeRef = useRef(activeId)

  const activate = useCallback((id: string | null) => {
    activeRef.current = id
    setActiveId(id)
  }, [])

  const refresh = useCallback(() => {
    client.listConversations().then(setConversations, () => {})
  }, [client])

  useEffect(() => {
    let cancelled = false
    client.listConversations().then((list) => !cancelled && setConversations(list), () => {})
    return () => {
      cancelled = true
    }
  }, [client])

  // Keep the open conversation in the URL so a reload reopens it.
  useEffect(() => {
    const hash = activeId ? `#c=${activeId}` : ''
    if (window.location.hash !== hash) {
      window.history.replaceState(null, '', hash || window.location.pathname + window.location.search)
    }
  }, [activeId])

  /** The conversation to save into; a new one is created lazily on the first message. */
  const ensureActive = useCallback(async () => {
    if (activeRef.current) return activeRef.current
    const created = await client.createConversation()
    activate(created.id)
    setConversations((prev) => [created, ...prev])
    return created.id
  }, [client, activate])

  const open = useCallback(
    async (id: string): Promise<ConversationDetail> => {
      const detail = await client.getConversation(id)
      activate(id)
      return detail
    },
    [client, activate],
  )

  const startNew = useCallback(() => activate(null), [activate])

  const rename = useCallback(
    async (id: string, title: string) => {
      try {
        const updated = await client.renameConversation(id, title)
        setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)))
      } catch (e) {
        onError(`Could not rename: ${e instanceof Error ? e.message : e}`)
      }
    },
    [client, onError],
  )

  /** Returns true if the deleted conversation was the open one. */
  const remove = useCallback(
    async (id: string) => {
      await client.deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      const wasActive = activeRef.current === id
      if (wasActive) activate(null)
      return wasActive
    },
    [client, activate],
  )

  const removeAll = useCallback(async () => {
    await client.deleteAllConversations()
    setConversations([])
    activate(null)
  }, [client, activate])

  return { conversations, activeId, ensureActive, open, startNew, rename, remove, removeAll, refresh }
}
