import ReactMarkdown, { type Components } from 'react-markdown'

import { citationNumber, linkCitations } from './citations'

type Props = { text: string; onCite?: (n: number) => void }

// Model output is rendered as Markdown without raw HTML (react-markdown ignores HTML by default).
export function Markdown({ text, onCite }: Props) {
  const components: Components = {
    p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="mb-3 list-disc pl-5 last:mb-0">{children}</ul>,
    ol: ({ children }) => <ol className="mb-3 list-decimal pl-5 last:mb-0">{children}</ol>,
    strong: ({ children }) => <strong className="font-semibold text-gator-blue-dark">{children}</strong>,
    a: ({ href, children }) => {
      const n = citationNumber(href)
      if (n === null) {
        return (
          <a href={href} rel="noreferrer noopener" className="text-gator-blue underline">
            {children}
          </a>
        )
      }
      return (
        <button
          type="button"
          onClick={() => onCite?.(n)}
          aria-label={`Show source ${n}`}
          className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-gator-blue px-1 align-text-top text-xs font-bold text-white hover:bg-gator-blue-dark"
        >
          {n}
        </button>
      )
    },
  }
  return <ReactMarkdown components={components}>{linkCitations(text)}</ReactMarkdown>
}
