import { Markdown } from './Markdown'

type Props = { category?: string; text: string }

export function EmergencyAlert({ category, text }: Props) {
  const crisis = category === 'self_harm'
  return (
    <div role="alert" className="rounded-xl border-2 border-alert-red bg-alert-tint p-4 text-slate-900 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-bold text-alert-red">
        <span aria-hidden>🚨</span> {crisis ? 'Please reach out for help now' : 'This may be an emergency'}
      </h2>
      <div className="mt-2 text-base">
        <Markdown text={text} />
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <a href="tel:911" className="rounded-lg bg-alert-red px-5 py-2.5 text-lg font-bold text-white hover:bg-red-800">
          Call 911
        </a>
        {crisis && (
          <a href="tel:988" className="rounded-lg border-2 border-alert-red bg-white px-5 py-2.5 text-lg font-bold text-alert-red hover:bg-red-50">
            Call or text 988
          </a>
        )}
      </div>
    </div>
  )
}
