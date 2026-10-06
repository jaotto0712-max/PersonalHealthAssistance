import { type ReactNode, useState } from 'react'

type Tab = 'chats' | 'documents'
type Props = { chats: ReactNode; documents: ReactNode; documentCount: number; onClose?: () => void }

export function Sidebar({ chats, documents, documentCount, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('chats')
  const tabs: [Tab, string][] = [
    ['chats', 'Chats'],
    ['documents', `Documents${documentCount ? ` (${documentCount})` : ''}`],
  ]
  return (
    <div className="flex h-full flex-col">
      <div role="tablist" aria-label="Sidebar" className="flex items-center gap-1 border-b border-slate-200 px-3 pt-3">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            onClick={() => setTab(id)}
            className={`-mb-px rounded-t-md border-b-2 px-3 py-2 text-sm font-semibold ${
              tab === id ? 'border-gator-orange text-gator-blue-dark' : 'border-transparent text-slate-600 hover:text-gator-blue'
            }`}
          >
            {label}
          </button>
        ))}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto rounded-md px-2 py-1 text-lg font-bold text-slate-600 hover:bg-slate-100 md:hidden"
          >
            ✕
          </button>
        )}
      </div>
      {tabs.map(([id]) => (
        <div
          key={id}
          role="tabpanel"
          id={`panel-${id}`}
          aria-labelledby={`tab-${id}`}
          hidden={tab !== id}
          className="min-h-0 flex-1"
        >
          {id === 'chats' ? chats : documents}
        </div>
      ))}
    </div>
  )
}
