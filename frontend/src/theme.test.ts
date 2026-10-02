import { describe, expect, it } from 'vitest'

import css from './index.css?raw'

const tokens = Object.fromEntries([...css.matchAll(/--color-([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]))
const color = (name: string) => (name === 'white' ? '#ffffff' : tokens[name])

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(fg: string, bg: string): number {
  const [hi, lo] = [luminance(color(fg)), luminance(color(bg))].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

// [foreground, background] pairs actually used in the UI.
const NORMAL_TEXT: [string, string][] = [
  ['gator-blue', 'white'],
  ['gator-blue-dark', 'white'],
  ['white', 'gator-blue'],
  ['white', 'gator-blue-dark'],
  ['gator-blue-dark', 'gator-orange-tint'],
  ['gator-blue', 'gator-blue-tint'],
  ['alert-red', 'white'],
  ['alert-red', 'alert-tint'],
  ['white', 'alert-red'],
]
// White on UF Orange only passes as large text (>= 18.66px bold): Send button uses 20px bold.
const LARGE_TEXT_OR_UI: [string, string][] = [
  ['white', 'gator-orange'],
  ['gator-orange', 'white'], // borders, focus ring, upload progress
  ['gator-orange', 'gator-blue'], // header bottom border against blue
]

describe('UF theme tokens', () => {
  it('defines the official UF Orange and UF Blue', () => {
    expect(tokens['gator-orange'].toLowerCase()).toBe('#fa4616')
    expect(tokens['gator-blue'].toLowerCase()).toBe('#0021a5')
  })

  it.each(NORMAL_TEXT)('%s on %s meets AA for normal text (4.5:1)', (fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5)
  })

  it.each(LARGE_TEXT_OR_UI)('%s on %s meets AA for large text / UI components (3:1)', (fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(3)
  })

  it('UF Orange is NOT body-text safe on white (guards against misuse)', () => {
    expect(contrast('gator-orange', 'white')).toBeLessThan(4.5)
  })
})
