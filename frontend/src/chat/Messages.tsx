import { useState } from 'react'

import type { ChatMessage } from './chatState'
import { EmergencyAlert } from './EmergencyAlert'
import { Markdown } from './Markdown'
import { SourcesDisclosure } from './SourcesDisclosure'

export function UserBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-gator-blue px-4 py-2.5 text-white shadow-sm">
        {message.content}
      </div>
    </div>
  )
}

export function AssistantBubble({ message }: { message: ChatMessage }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [highlighted, setHighlighted] = useState<number | null>(null)

  if (message.emergency) return <EmergencyAlert category={message.emergency.category} text={message.content} />

  const sources = message.sources ?? []
  const waiting = message.status === 'streaming' && message.content === ''
  const cite = (n: number) => {
    if (!sources.some((s) => s.n === n)) return
    setSourcesOpen(true)
    setHighlighted(n)
  }

  return (
    <div className="flex justify-start" aria-busy={message.status === 'streaming'}>
      <div className="max-w-[85%] break-words rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm">
        {waiting ? (
          <p className="text-slate-600">
            <span className="animate-pulse">Thinking…</span>
          </p>
        ) : (
          <Markdown text={message.content} onCite={cite} />
        )}
        {message.status === 'stopped' && (
          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Stopped</p>
        )}
        {message.status === 'error' && (
          <p className="mt-2 text-sm font-semibold text-alert-red">⚠ {message.error ?? 'Something went wrong.'}</p>
        )}
        {sources.length > 0 && (
          <SourcesDisclosure
            messageId={message.id}
            sources={sources}
            open={sourcesOpen}
            highlighted={highlighted}
            onToggle={() => setSourcesOpen((o) => !o)}
          />
        )}
      </div>
    </div>
  )
}
