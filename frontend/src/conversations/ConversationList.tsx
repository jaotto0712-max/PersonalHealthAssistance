import { type FormEvent, useState } from 'react'

import type { ConversationSummary } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { relativeTime } from './relativeTime'

type Props = {
  conversations: ConversationSummary[]
  activeId: string | null
  onOpen: (id: string) => void
  onNew: () => void
  onRename: (id: string, title: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onDeleteAll: () => Promise<void>
}

export function ConversationList(props: Props) {
  const { conversations, activeId, onOpen, onNew, onRename, onDelete, onDeleteAll } = props
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirmAll, setConfirmAll] = useState(false)

  const saveRename = async (e: FormEvent) => {
    e.preventDefault()
    if (editing && draft.trim()) await onRename(editing, draft.trim())
    setEditing(null)
  }

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wide text-gator-blue-dark">Saved chats</h2>
        <p className="text-xs text-slate-600">Stored only on this device.</p>
      </div>
      <button
        type="button"
        onClick={onNew}
        className="rounded-md bg-gator-blue px-3 py-2 text-sm font-semibold text-white hover:bg-gator-blue-dark"
      >
        + New chat
      </button>

      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Saved chats">
        {conversations.map((c) => {
          const active = c.id === activeId
          const title = c.title ?? 'New chat'
          return (
            <li
              key={c.id}
              className={`group flex items-center gap-1 rounded-md border text-sm ${
                active ? 'border-gator-blue bg-gator-blue-tint' : 'border-transparent hover:bg-slate-100'
              }`}
            >
              {editing === c.id ? (
                <form onSubmit={saveRename} className="flex flex-1 gap-1 p-1">
                  <label htmlFor={`rename-${c.id}`} className="sr-only">
                    Rename chat
                  </label>
                  <input
                    id={`rename-${c.id}`}
                    autoFocus
                    value={draft}
                    maxLength={120}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => e.key === 'Escape' && setEditing(null)}
                    className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                  />
                  <button type="submit" className="rounded px-2 text-sm font-semibold text-gator-blue">
                    Save
                  </button>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onOpen(c.id)}
                    aria-current={active ? 'true' : undefined}
                    className="min-w-0 flex-1 px-2 py-1.5 text-left"
                  >
                    <span className="block truncate font-semibold text-slate-900">{title}</span>
                    <span className="block text-xs text-slate-600">{relativeTime(c.updated_at)}</span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Rename ${title}`}
                    onClick={() => {
                      setEditing(c.id)
                      setDraft(title)
                    }}
                    className="rounded p-1 text-slate-600 hover:text-gator-blue"
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${title}`}
                    onClick={() => onDelete(c.id)}
                    className="rounded p-1 text-slate-600 hover:text-alert-red"
                  >
                    🗑
                  </button>
                </>
              )}
            </li>
          )
        })}
        {conversations.length === 0 && (
          <li className="text-sm text-slate-600">
            No saved chats yet. Ask a question to start one; upload lab reports in the Documents tab.
          </li>
        )}
      </ul>

      {conversations.length > 0 && (
        <button
          type="button"
          onClick={() => setConfirmAll(true)}
          className="self-start text-sm font-semibold text-alert-red hover:underline"
        >
          Delete all chats
        </button>
      )}
      {confirmAll && (
        <ConfirmDialog
          title="Delete all chats?"
          body="This permanently deletes every saved conversation from this device. Your documents are not affected."
          confirmLabel="Delete all"
          onConfirm={async () => {
            setConfirmAll(false)
            await onDeleteAll()
          }}
          onCancel={() => setConfirmAll(false)}
        />
      )}
    </div>
  )
}
