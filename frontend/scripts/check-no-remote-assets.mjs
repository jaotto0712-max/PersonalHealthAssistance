// Fails if the production build loads any asset from a remote origin.
// Only *loading* references count (src/href attributes, CSS url()/@import, JS imports);
// plain strings such as SVG xmlns or React's error-doc links are not network requests.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'

const distDir = process.argv[2] ?? 'dist'
const REMOTE = String.raw`(?:https?:)?//(?!localhost[:/]|127\.0\.0\.1[:/])`
const patterns = {
  '.html': [new RegExp(String.raw`\b(?:src|href|srcset)\s*=\s*["']?${REMOTE}`, 'gi')],
  '.css': [
    new RegExp(String.raw`url\(\s*["']?${REMOTE}`, 'gi'),
    new RegExp(String.raw`@import\s+(?:url\()?\s*["']${REMOTE}`, 'gi'),
  ],
  '.js': [
    new RegExp(String.raw`\bimport\s*\(\s*["'\`]${REMOTE}`, 'g'),
    new RegExp(String.raw`\bfrom\s*["']${REMOTE}`, 'g'),
  ],
}

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) yield* walk(p)
    else yield p
  }
}

let failures = 0
for (const file of walk(distDir)) {
  const checks = patterns[extname(file)]
  if (!checks) continue
  const text = readFileSync(file, 'utf8')
  for (const re of checks) {
    for (const m of text.matchAll(re)) {
      const line = text.slice(0, m.index).split('\n').length
      const snippet = text.slice(m.index, m.index + 80).replace(/\s+/g, ' ')
      console.error(`remote asset: ${relative(process.cwd(), file)}:${line}: ${snippet}`)
      failures++
    }
  }
}

if (failures) {
  console.error(`\n${failures} remote asset reference(s) found — the app must work fully offline.`)
  process.exit(1)
}
console.log(`OK: no remote asset references in ${distDir}/`)
