import { type DragEvent, useRef, useState } from 'react'

import { ALLOWED_EXTENSIONS, type DocumentRecord } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import type { UploadError, UploadProgress } from './useDocuments'

type Props = {
  documents: DocumentRecord[]
  uploads: UploadProgress[]
  errors: UploadError[]
  loadError: string | null
  onUpload: (files: File[]) => void
  onDelete: (id: string) => Promise<void>
  onClear: () => Promise<void>
  onDismissError: (key: string) => void
  onFailure: (message: string) => void
  /** Shown in the mobile drawer only. */
  onClose?: () => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentPanel(props: Props) {
  const { documents, uploads, errors, loadError, onUpload, onDelete, onClear, onDismissError, onFailure, onClose } = props
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [deleting, setDeleting] = useState<Set<string>>(new Set())
  const [confirmClear, setConfirmClear] = useState(false)

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) onUpload([...e.dataTransfer.files])
  }

  const remove = async (doc: DocumentRecord) => {
    setDeleting((s) => new Set(s).add(doc.id))
    try {
      await onDelete(doc.id)
    } catch (e) {
      onFailure(`Could not delete ${doc.filename}: ${e instanceof Error ? e.message : e}`)
    } finally {
      setDeleting((s) => {
        const next = new Set(s)
        next.delete(doc.id)
        return next
      })
    }
  }

  const clearAll = async () => {
    setConfirmClear(false)
    try {
      await onClear()
    } catch (e) {
      onFailure(`Could not clear documents: ${e instanceof Error ? e.message : e}`)
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wide text-gator-blue-dark">My documents</h2>
          <p className="text-xs text-slate-600">Stored only on this device.</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close documents"
            className="rounded-md px-2 py-1 text-lg font-bold text-slate-600 hover:bg-slate-100 md:hidden"
          >
            ✕
          </button>
        )}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-xl border-2 border-dashed p-4 text-center transition-colors ${
          dragging ? 'border-gator-orange bg-gator-orange-tint' : 'border-slate-300 bg-slate-50'
        }`}
      >
        <p className="text-sm text-slate-700">Drop files here or</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-1 rounded-md bg-gator-blue px-3 py-1.5 text-sm font-semibold text-white hover:bg-gator-blue-dark"
        >
          Browse files
        </button>
        <p className="mt-2 text-xs text-slate-600">PDF, TXT, MD, or DOCX · up to 20 MB</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          aria-label="Upload documents"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) onUpload([...e.target.files])
            e.target.value = ''
          }}
        />
      </div>

      {errors.length > 0 && (
        <ul className="space-y-2">
          {errors.map((err) => (
            <li key={err.key} role="alert" className="flex items-start gap-2 rounded-md border border-red-200 bg-alert-tint p-2 text-sm text-alert-red">
              <p className="min-w-0 flex-1 break-words">
                <strong>{err.filename}</strong>: {err.reason}
              </p>
              <button type="button" onClick={() => onDismissError(err.key)} aria-label={`Dismiss error for ${err.filename}`} className="font-bold">
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {loadError && <p className="text-sm text-alert-red">Could not load documents: {loadError}</p>}

      <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto" aria-label="Uploaded documents">
        {uploads.map((u) => (
          <li key={u.key} className="rounded-md border border-slate-200 bg-white p-2 text-sm">
            <p className="truncate font-semibold text-slate-800">{u.filename}</p>
            <div
              role="progressbar"
              aria-label={`Uploading ${u.filename}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(u.progress * 100)}
              className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"
            >
              <div className="h-full bg-gator-orange transition-all" style={{ width: `${u.progress * 100}%` }} />
            </div>
          </li>
        ))}
        {documents.map((doc) => (
          <li key={doc.id} className="flex items-start gap-2 rounded-md border border-slate-200 bg-white p-2 text-sm">
            <span aria-hidden className="mt-0.5">📄</span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-slate-900" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-xs text-slate-600">
                {doc.pages} {doc.pages === 1 ? 'page' : 'pages'} · {formatSize(doc.size_bytes)}
              </p>
              {doc.status === 'indexed' ? (
                <p className="mt-0.5 text-xs font-semibold text-green-800">✓ Ready</p>
              ) : (
                <p className="mt-0.5 text-xs font-semibold text-amber-800">⚠ Text could not be read (scanned PDF?). Not searchable.</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => remove(doc)}
              disabled={deleting.has(doc.id)}
              aria-label={`Delete ${doc.filename}`}
              className="rounded p-1 text-slate-600 hover:bg-red-50 hover:text-alert-red disabled:opacity-50"
            >
              🗑
            </button>
          </li>
        ))}
        {documents.length === 0 && uploads.length === 0 && (
          <li className="text-sm text-slate-600">No documents yet. Upload a lab report or visit summary to ask about it.</li>
        )}
      </ul>

      {documents.length > 0 && (
        <button
          type="button"
          onClick={() => setConfirmClear(true)}
          className="self-start text-sm font-semibold text-alert-red hover:underline"
        >
          Clear all documents
        </button>
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Remove all documents?"
          body="This deletes every uploaded file and its search index from this device. This cannot be undone."
          confirmLabel="Remove all"
          onConfirm={clearAll}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </div>
  )
}
