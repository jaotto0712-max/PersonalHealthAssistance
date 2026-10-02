import { useEffect } from 'react'

type Props = { message: string | null; onDismiss: () => void }

export function Toast({ message, onDismiss }: Props) {
  useEffect(() => {
    if (!message) return
    const timer = setTimeout(onDismiss, 8000)
    return () => clearTimeout(timer)
  }, [message, onDismiss])

  if (!message) return null
  return (
    <div
      role="alert"
      className="fixed bottom-20 right-4 z-50 flex max-w-sm items-start gap-3 rounded-lg border-l-4 border-alert-red bg-white px-4 py-3 text-sm text-slate-900 shadow-lg"
    >
      <p className="flex-1">{message}</p>
      <button type="button" onClick={onDismiss} aria-label="Dismiss notification" className="font-bold text-slate-600 hover:text-slate-900">
        ✕
      </button>
    </div>
  )
}
