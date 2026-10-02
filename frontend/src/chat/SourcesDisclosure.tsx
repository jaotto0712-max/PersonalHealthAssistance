import { useEffect, useRef } from 'react'

import type { Source } from '../api/types'

type Props = {
  messageId: string
  sources: Source[]
  open: boolean
  highlighted: number | null
  onToggle: () => void
}

function SourceItem({ source, highlighted }: { source: Source; highlighted: boolean }) {
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (highlighted) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [highlighted])
  return (
    <li
      ref={ref}
      data-highlighted={highlighted || undefined}
      className={`rounded-md border bg-white p-2 text-sm ${highlighted ? 'border-gator-orange ring-2 ring-gator-orange' : 'border-slate-200'}`}
    >
      <div className="flex items-baseline gap-2">
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-gator-blue px-1 text-xs font-bold text-white">
          {source.n}
        </span>
        <span className="truncate font-semibold text-gator-blue-dark">{source.filename}</span>
        <span className="shrink-0 text-slate-600">p. {source.page}</span>
      </div>
      <p className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-slate-700">“{source.snippet}”</p>
    </li>
  )
}

export function SourcesDisclosure({ messageId, sources, open, highlighted, onToggle }: Props) {
  const cited = sources.filter((s) => s.cited)
  const related = sources.filter((s) => !s.cited)
  const panelId = `sources-${messageId}`
  const label = cited.length ? `Sources (${cited.length})` : `Related documents (${related.length})`

  return (
    <div className="mt-3 border-t border-slate-200 pt-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className="text-sm font-semibold text-gator-blue hover:underline"
      >
        {open ? '▾' : '▸'} {label}
      </button>
      {open && (
        <div id={panelId} className="mt-2 space-y-3">
          {cited.length > 0 && (
            <section aria-label="Sources">
              <ul className="space-y-2">
                {cited.map((s) => (
                  <SourceItem key={s.n} source={s} highlighted={highlighted === s.n} />
                ))}
              </ul>
            </section>
          )}
          {related.length > 0 && (
            <section aria-label="Related documents">
              {cited.length > 0 && <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">Related documents</h3>}
              <ul className="space-y-2">
                {related.map((s) => (
                  <SourceItem key={s.n} source={s} highlighted={highlighted === s.n} />
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
