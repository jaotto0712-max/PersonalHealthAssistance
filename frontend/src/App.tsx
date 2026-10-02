import { useCallback, useState } from 'react'

import { api, isMockApi } from './api'
import type { ApiClient } from './api/types'
import { ChatThread } from './chat/ChatThread'
import { Composer } from './chat/Composer'
import { useChat } from './chat/useChat'
import { DisclaimerBanner } from './components/DisclaimerBanner'
import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { Toast } from './components/Toast'
import { DocumentPanel } from './documents/DocumentPanel'
import { useDocuments } from './documents/useDocuments'
import { type BackendStatus, useHealth } from './hooks/useHealth'
import { useMediaQuery } from './hooks/useMediaQuery'

function disabledReason(status: BackendStatus): string | null {
  if (status.kind === 'checking') return null
  if (status.kind === 'offline') return "Can't reach the backend. Start it with `make dev`, then try again."
  const { llm, model } = status.health
  if (llm === 'unavailable') return 'Ollama is not running. Start it with `ollama serve`, then try again.'
  if (llm === 'model_missing') return `The model "${model ?? 'unknown'}" is not installed in Ollama. See the README to set it up.`
  return null
}

type Props = { client?: ApiClient; isMock?: boolean }

export default function App({ client = api, isMock = isMockApi }: Props) {
  const [toast, setToast] = useState<string | null>(null)
  const showError = useCallback((message: string) => setToast(message), [])
  const dismissToast = useCallback(() => setToast(null), [])

  const { status, canChat } = useHealth(client)
  const chat = useChat(client, showError)
  const docs = useDocuments(client)

  const isDesktop = useMediaQuery('(min-width: 768px)')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawerVisible = isDesktop || drawerOpen

  return (
    <div className="flex h-dvh flex-col bg-slate-50 font-sans text-slate-900">
      <Header
        status={status}
        isMock={isMock}
        documentCount={docs.documents.length}
        onNewChat={chat.reset}
        onToggleDocuments={() => setDrawerOpen((o) => !o)}
      />
      <DisclaimerBanner />

      <div className="relative flex min-h-0 flex-1">
        {drawerOpen && !isDesktop && (
          <div aria-hidden className="fixed inset-0 z-30 bg-slate-900/40" onClick={() => setDrawerOpen(false)} />
        )}
        <aside
          aria-label="Documents"
          inert={!drawerVisible}
          className={`fixed inset-y-0 left-0 z-40 w-80 max-w-[85vw] border-r border-slate-200 bg-white shadow-xl transition-transform md:static md:z-auto md:translate-x-0 md:shadow-none ${
            drawerVisible ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <DocumentPanel
            documents={docs.documents}
            uploads={docs.uploads}
            errors={docs.errors}
            loadError={docs.loadError}
            onUpload={docs.upload}
            onDelete={docs.remove}
            onClear={docs.clear}
            onDismissError={docs.dismissError}
            onFailure={showError}
            onClose={() => setDrawerOpen(false)}
          />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <ChatThread messages={chat.messages} canSend={canChat && !chat.isStreaming} onSuggestion={chat.send} />
          <Composer
            isStreaming={chat.isStreaming}
            disabledReason={disabledReason(status)}
            onSend={chat.send}
            onStop={chat.stop}
          />
        </main>
      </div>

      <Footer />
      <Toast message={toast} onDismiss={dismissToast} />
    </div>
  )
}
