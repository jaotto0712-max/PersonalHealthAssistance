import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axe from 'axe-core'
import { expect, it } from 'vitest'

import App from './App'
import { doc, fakeClient } from './test/fakeClient'

it('main screen has no axe violations (with a conversation, sources, and documents)', async () => {
  const client = fakeClient({
    docs: [doc(), doc({ filename: 'scan.pdf', status: 'needs_ocr' })],
    async *chat() {
      yield { type: 'token', data: { text: 'Your LDL was **162 mg/dL** [1].' } }
      yield { type: 'sources', data: { items: [{ n: 1, doc_id: 'd', filename: 'labs.pdf', page: 2, score: 0.8, snippet: 'LDL 162', cited: true }] } }
      yield { type: 'done', data: { disclaimer: '' } }
    },
  })
  const { container } = render(<App client={client} isMock />)
  const user = userEvent.setup()
  await user.type(await screen.findByRole('textbox', { name: /ask about your health/i }), 'Is my LDL high?{Enter}')
  await user.click(await screen.findByRole('button', { name: 'Show source 1' }))

  // jsdom has no layout engine, so axe cannot compute color contrast; theme.test.ts covers it.
  const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } })
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([])
})
