import { type FormEvent, type KeyboardEvent, useState } from 'react'

import { MAX_MESSAGE_CHARS } from '../api/types'

type Props = {
  isStreaming: boolean
  disabledReason: string | null
  onSend: (text: string) => void
  onStop: () => void
}

export function Composer({ isStreaming, disabledReason, onSend, onStop }: Props) {
  const [text, setText] = useState('')
  const disabled = disabledReason !== null
  const canSubmit = !disabled && !isStreaming && text.trim().length > 0 && text.length <= MAX_MESSAGE_CHARS

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!canSubmit) return
    onSend(text)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} className="border-t border-slate-200 bg-white px-4 py-3">
      {disabledReason && (
        <p role="status" className="mx-auto mb-2 max-w-3xl rounded-md bg-alert-tint px-3 py-2 text-sm text-alert-red">
          {disabledReason}
        </p>
      )}
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <label htmlFor="composer" className="sr-only">
          Ask about your health
        </label>
        <textarea
          id="composer"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          maxLength={MAX_MESSAGE_CHARS}
          placeholder="Ask about your health…"
          className="field-sizing-content max-h-40 min-h-12 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-base text-slate-900 placeholder:text-slate-500 focus:border-gator-blue disabled:cursor-not-allowed disabled:bg-slate-100"
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="h-12 rounded-xl border-2 border-gator-blue bg-white px-5 text-xl font-bold text-gator-blue hover:bg-gator-blue-tint"
          >
            ■ Stop
          </button>
        ) : (
          // UF Orange with white text is only AA-compliant as large text: keep this label >= 20px bold.
          <button
            type="submit"
            disabled={!canSubmit}
            className="h-12 rounded-xl bg-gator-orange px-5 text-xl font-bold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send ▶
          </button>
        )}
      </div>
      {text.length > MAX_MESSAGE_CHARS - 200 && (
        <p className="mx-auto mt-1 max-w-3xl text-right text-xs text-slate-600">
          {text.length}/{MAX_MESSAGE_CHARS}
        </p>
      )}
    </form>
  )
}
