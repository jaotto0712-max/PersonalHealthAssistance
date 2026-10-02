/** Turn `[n]` citation markers into `#cite-n` links that the renderer shows as chips. */
export function linkCitations(text: string): string {
  return text.replace(/\[(\d{1,2})\](?![([])/g, '[$1](#cite-$1)')
}

export function citationNumber(href: string | undefined): number | null {
  const match = href?.match(/^#cite-(\d+)$/)
  return match ? Number(match[1]) : null
}
