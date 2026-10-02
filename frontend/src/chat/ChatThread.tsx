import { useEffect, useRef } from 'react'

import { GatorMascot } from '../components/GatorMascot'
import type { ChatMessage } from './chatState'
import { AssistantBubble, UserBubble } from './Messages'

const SUGGESTIONS = [
  'What does my cholesterol result mean?',
  'What are common side effects of metformin?',
  'How can I lower my blood pressure?',
]

type Props = { messages: ChatMessage[]; canSend: boolean; onSuggestion: (text: string) => void }

export function ChatThread({ messages, canSend, onSuggestion }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  useEffect(() => {
    const el = scrollRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [messages])

  const onScroll = () => {
    const el = scrollRef.current
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  return (
    <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
      {messages.length === 0 ? (
        <div className="mx-auto flex max-w-xl flex-col items-center pt-6 text-center">
          <GatorMascot className="h-24 w-24" title="Gator mascot" />
          <h2 className="mt-4 text-2xl font-bold text-gator-blue-dark">Hi! How can I help with your health today?</h2>
          <p className="mt-2 text-slate-700">
            Ask a general health question, or upload a lab report or visit summary and ask about it. Answers cite the
            documents they come from.
          </p>
          <ul className="mt-6 flex flex-wrap justify-center gap-2" aria-label="Example questions">
            {SUGGESTIONS.map((s) => (
              <li key={s}>
                <button
                  type="button"
                  disabled={!canSend}
                  onClick={() => onSuggestion(s)}
                  className="rounded-full border border-gator-blue px-4 py-1.5 text-sm text-gator-blue hover:bg-gator-blue-tint disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ol className="mx-auto flex max-w-3xl flex-col gap-4" aria-label="Conversation">
          {messages.map((m) => (
            <li key={m.id}>{m.role === 'user' ? <UserBubble message={m} /> : <AssistantBubble message={m} />}</li>
          ))}
        </ol>
      )}
    </div>
  )
}
