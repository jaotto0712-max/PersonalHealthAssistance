import type { BackendStatus } from '../hooks/useHealth'
import { GatorMascot } from './GatorMascot'

type Props = {
  status: BackendStatus
  isMock: boolean
  documentCount: number
  onNewChat: () => void
  onToggleDocuments: () => void
}

function statusInfo(status: BackendStatus): { label: string; dot: string } {
  if (status.kind === 'checking') return { label: 'Checking backend…', dot: 'bg-slate-300' }
  if (status.kind === 'offline') return { label: 'Backend offline', dot: 'bg-red-400' }
  const { llm, model } = status.health
  if (llm === 'unavailable') return { label: 'Ollama not running', dot: 'bg-red-400' }
  if (llm === 'model_missing') return { label: `Model not installed${model ? `: ${model}` : ''}`, dot: 'bg-red-400' }
  if (llm === 'ok') return { label: `Model ready${model ? ` · ${model}` : ''}`, dot: 'bg-green-400' }
  return { label: 'Backend connected', dot: 'bg-amber-300' }
}

export function Header({ status, isMock, documentCount, onNewChat, onToggleDocuments }: Props) {
  const { label, dot } = statusInfo(status)
  return (
    <header className="flex items-center gap-3 border-b-4 border-gator-orange bg-gator-blue px-4 py-2.5 text-white">
      <GatorMascot className="h-10 w-10 shrink-0 sm:h-11 sm:w-11" title="Personal Health Assistant gator" />
      <div className="min-w-0 flex-1">
        <h1 className="text-base font-bold leading-tight sm:text-xl">Personal Health Assistant</h1>
        <p className="hidden text-sm text-blue-100 sm:block">AI Passport Capstone · runs entirely on this device</p>
      </div>
      <div
        role="status"
        aria-label={`Backend status: ${label}`}
        className="hidden items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-sm sm:flex"
      >
        <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <span>{label}</span>
        {isMock && <span className="rounded bg-white px-1.5 text-xs font-bold uppercase text-gator-blue">Mock API</span>}
      </div>
      <span aria-hidden className={`h-3 w-3 rounded-full sm:hidden ${dot}`} title={label} />
      <button
        type="button"
        onClick={onToggleDocuments}
        className="shrink-0 rounded-md border border-white/60 px-2 py-1 text-sm font-semibold hover:bg-white/10 sm:px-3 sm:py-1.5 md:hidden"
      >
        Docs{documentCount ? ` (${documentCount})` : ''}
      </button>
      <button
        type="button"
        onClick={onNewChat}
        className="shrink-0 rounded-md border border-white/60 px-2 py-1 text-sm font-semibold hover:bg-white/10 sm:px-3 sm:py-1.5"
      >
        New chat
      </button>
    </header>
  )
}
