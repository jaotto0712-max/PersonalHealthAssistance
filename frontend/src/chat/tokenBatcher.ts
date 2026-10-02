/** Coalesces streamed tokens and flushes them at most once per animation frame. */
export function createTokenBatcher(flush: (text: string) => void) {
  let pending = ''
  let scheduled: number | null = null
  const schedule =
    typeof requestAnimationFrame === 'function'
      ? (cb: () => void) => requestAnimationFrame(cb)
      : (cb: () => void) => window.setTimeout(cb, 16)
  const cancel =
    typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : (id: number) => clearTimeout(id)

  const drain = () => {
    scheduled = null
    if (pending) {
      const text = pending
      pending = ''
      flush(text)
    }
  }

  return {
    push(text: string) {
      pending += text
      scheduled ??= schedule(drain)
    },
    /** Flush synchronously (before sources/done/error so ordering is preserved). */
    flush() {
      if (scheduled !== null) cancel(scheduled)
      drain()
    },
  }
}
