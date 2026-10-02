import { useEffect, useState } from 'react'

import type { ApiClient, Health } from '../api/types'

export type BackendStatus =
  | { kind: 'checking' }
  | { kind: 'offline' }
  | { kind: 'ready'; health: Health }

/** Polls GET /api/health. `canChat` is false only when we know chatting cannot work. */
export function useHealth(client: ApiClient, intervalMs = 15_000) {
  const [status, setStatus] = useState<BackendStatus>({ kind: 'checking' })

  useEffect(() => {
    let cancelled = false
    const check = () =>
      client.health().then(
        (health) => !cancelled && setStatus({ kind: 'ready', health }),
        () => !cancelled && setStatus({ kind: 'offline' }),
      )
    void check()
    const timer = setInterval(check, intervalMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [client, intervalMs])

  const llm = status.kind === 'ready' ? status.health.llm : undefined
  const canChat = status.kind === 'ready' && llm !== 'unavailable' && llm !== 'model_missing'
  return { status, canChat }
}
