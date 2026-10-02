import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, type Source } from './api/types'
import App from './App'
import { controlledChat, doc, fakeClient } from './test/fakeClient'

const source = (n: number, cited: boolean, filename = 'labs.pdf'): Source => ({
  n,
  doc_id: 'd1',
  filename,
  page: n + 1,
  score: 0.8,
  snippet: `snippet ${n}`,
  cited,
})

async function ask(text: string) {
  const user = userEvent.setup()
  const box = await screen.findByRole('textbox', { name: /ask about your health/i })
  await waitFor(() => expect(box).toBeEnabled())
  await user.type(box, `${text}{Enter}`)
  return user
}

describe('chat', () => {
  it('streams an answer progressively, then shows cited and related sources', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    const user = await ask('Is my LDL high?')

    expect(screen.getByText('Is my LDL high?')).toBeInTheDocument()
    expect(await screen.findByText('Thinking…')).toBeInTheDocument()

    stream.push({ type: 'meta', data: { emergency: false, retrieved_count: 2 } }, { type: 'token', data: { text: 'Your LDL ' } })
    expect(await screen.findByText(/Your LDL/)).toBeInTheDocument()
    stream.push({ type: 'token', data: { text: 'was 162 mg/dL [1].' } })
    expect(await screen.findByText(/was 162 mg\/dL/)).toBeInTheDocument()

    stream.push(
      { type: 'sources', data: { items: [source(1, true), source(2, false, 'visit.txt')] } },
      { type: 'done', data: { disclaimer: 'Not medical advice' } },
    )
    stream.end()

    const toggle = await screen.findByRole('button', { name: /sources \(1\)/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(screen.getByRole('button', { name: 'Show source 1' }))
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const cited = within(screen.getByRole('region', { name: 'Sources' }))
    expect(cited.getByText('labs.pdf').closest('li')).toHaveAttribute('data-highlighted', 'true')
    const related = within(screen.getByRole('region', { name: 'Related documents' }))
    expect(related.getByText('visit.txt')).toBeInTheDocument()
  })

  it('lists only uncited sources under "Related documents"', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    const user = await ask('How do vaccines work?')
    stream.push(
      { type: 'token', data: { text: 'Vaccines train the immune system.' } },
      { type: 'sources', data: { items: [source(1, false)] } },
      { type: 'done', data: { disclaimer: '' } },
    )
    stream.end()
    await user.click(await screen.findByRole('button', { name: /related documents \(1\)/i }))
    expect(screen.queryByRole('region', { name: 'Sources' })).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Related documents' })).getByText('labs.pdf')).toBeInTheDocument()
  })

  it('renders an emergency alert card with 911 and 988 actions for self-harm', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    await ask('I want to end my life')
    stream.push(
      { type: 'meta', data: { emergency: true, category: 'self_harm' } },
      { type: 'token', data: { text: 'Please call or text 988 now.' } },
      { type: 'sources', data: { items: [] } },
      { type: 'done', data: { disclaimer: '' } },
    )
    stream.end()
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByRole('link', { name: 'Call 911' })).toHaveAttribute('href', 'tel:911')
    expect(within(alert).getByRole('link', { name: 'Call or text 988' })).toHaveAttribute('href', 'tel:988')
  })

  it('stops generation, keeps the partial answer marked as stopped, and re-enables input', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    const user = await ask('Tell me about diabetes')
    stream.push({ type: 'token', data: { text: 'Diabetes is a condition' } })
    expect(await screen.findByText(/Diabetes is a condition/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /stop/i }))
    expect(await screen.findByText('Stopped')).toBeInTheDocument()
    expect(screen.getByText(/Diabetes is a condition/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /ask about your health/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('shows an error toast and inline error for error events', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    await ask('hello')
    stream.push({ type: 'error', data: { code: 'llm_unavailable', message: 'Ollama is not running.' } })
    stream.end()
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama is not running.')
    expect(screen.getByText(/⚠ Ollama is not running\./)).toBeInTheDocument()
  })

  it('New chat clears the conversation', async () => {
    const stream = controlledChat()
    render(<App client={fakeClient({ chat: stream.chat })} isMock={false} />)
    const user = await ask('first question')
    stream.push({ type: 'token', data: { text: 'answer' } }, { type: 'done', data: { disclaimer: '' } })
    stream.end()
    expect(await screen.findByText('answer')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'New chat' }))
    expect(screen.queryByText('first question')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /how can i help/i })).toBeInTheDocument()
  })

  it('sends prior turns as history on follow-up questions', async () => {
    const calls: unknown[] = []
    const client = fakeClient({
      async *chat(req) {
        calls.push(req)
        yield { type: 'token', data: { text: `reply ${calls.length}` } }
        yield { type: 'done', data: { disclaimer: '' } }
      },
    })
    render(<App client={client} isMock={false} />)
    await ask('what is my LDL?')
    expect(await screen.findByText('reply 1')).toBeInTheDocument()
    await ask('what about HDL?')
    await screen.findByText('reply 2')
    expect(calls[1]).toEqual({
      message: 'what about HDL?',
      history: [
        { role: 'user', content: 'what is my LDL?' },
        { role: 'assistant', content: 'reply 1' },
      ],
    })
  })

  it('disables the composer and explains when Ollama is unavailable', async () => {
    render(<App client={fakeClient({ healthValue: { status: 'ok', version: 't', llm: 'unavailable' } })} isMock={false} />)
    expect(await screen.findByText(/Ollama is not running/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /ask about your health/i })).toBeDisabled()
    expect(screen.getByRole('status', { name: /backend status/i })).toHaveTextContent('Ollama not running')
  })
})

describe('documents', () => {
  it('uploads a file and lists it as ready', async () => {
    const user = userEvent.setup()
    render(<App client={fakeClient()} isMock={false} />)
    await user.upload(screen.getByLabelText('Upload documents'), new File(['x'], 'visit.txt', { type: 'text/plain' }))
    const list = screen.getByRole('list', { name: 'Uploaded documents' })
    expect(await within(list).findByText('visit.txt')).toBeInTheDocument()
    expect(within(list).getByText('✓ Ready')).toBeInTheDocument()
  })

  it('shows a readable error naming the file when the server rejects it', async () => {
    const user = userEvent.setup()
    const uploadDocument = vi.fn().mockRejectedValue(new ApiError(413, 'File is larger than the 20 MB limit.'))
    render(<App client={fakeClient({ uploadDocument })} isMock={false} />)
    await user.upload(screen.getByLabelText('Upload documents'), new File(['x'], 'huge.pdf', { type: 'application/pdf' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('huge.pdf')
    expect(alert).toHaveTextContent('larger than the 20 MB limit')
  })

  it('rejects unsupported types before uploading', async () => {
    const user = userEvent.setup({ applyAccept: false })
    const uploadDocument = vi.fn()
    render(<App client={fakeClient({ uploadDocument })} isMock={false} />)
    await user.upload(screen.getByLabelText('Upload documents'), new File(['x'], 'tool.exe'))
    expect(await screen.findByRole('alert')).toHaveTextContent(/tool\.exe.*Unsupported file type/)
    expect(uploadDocument).not.toHaveBeenCalled()
  })

  it('warns about documents that need OCR', async () => {
    render(<App client={fakeClient({ docs: [doc({ filename: 'scan.pdf', status: 'needs_ocr', chunks: 0 })] })} isMock={false} />)
    expect(await screen.findByText(/Text could not be read/)).toBeInTheDocument()
  })

  it('removes a document after the backend confirms deletion', async () => {
    const user = userEvent.setup()
    let release: () => void = () => {}
    const deleteDocument = vi.fn(() => new Promise<void>((r) => (release = r)))
    render(<App client={fakeClient({ docs: [doc({ id: 'd1', filename: 'labs.pdf' })], deleteDocument })} isMock={false} />)
    await user.click(await screen.findByRole('button', { name: 'Delete labs.pdf' }))
    expect(deleteDocument).toHaveBeenCalledWith('d1')
    expect(screen.getByText('labs.pdf')).toBeInTheDocument() // still listed until confirmed
    release()
    await waitFor(() => expect(screen.queryByText('labs.pdf')).not.toBeInTheDocument())
  })

  it('clears all documents only after confirmation', async () => {
    const user = userEvent.setup()
    const clearDocuments = vi.fn().mockResolvedValue(undefined)
    render(<App client={fakeClient({ docs: [doc(), doc({ filename: 'visit.txt' })], clearDocuments })} isMock={false} />)
    await user.click(await screen.findByRole('button', { name: 'Clear all documents' }))
    const dialog = screen.getByRole('dialog', { name: 'Remove all documents?' })
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(clearDocuments).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Clear all documents' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove all' }))
    expect(clearDocuments).toHaveBeenCalledOnce()
    await waitFor(() => expect(screen.getByText(/No documents yet/)).toBeInTheDocument())
  })
})

describe('layout', () => {
  it('always shows the disclaimer banner and non-affiliation footer', async () => {
    render(<App client={fakeClient()} isMock={false} />)
    expect(screen.getByRole('note', { name: 'Medical disclaimer' })).toHaveTextContent(/not medical advice.*911/i)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(/not affiliated with or endorsed by the University of Florida or UF Health/)
  })
})

describe('mobile documents drawer', () => {
  it('opens from the header and closes with its close button', async () => {
    const user = userEvent.setup()
    render(<App client={fakeClient({ docs: [doc()] })} isMock={false} />)
    const drawer = screen.getByRole('complementary', { name: 'Documents', hidden: true })
    expect(drawer).toHaveAttribute('inert') // jsdom matchMedia reports mobile width
    await user.click(await screen.findByRole('button', { name: 'Docs (1)' }))
    expect(drawer).not.toHaveAttribute('inert')
    await user.click(within(drawer).getByRole('button', { name: 'Close documents' }))
    expect(drawer).toHaveAttribute('inert')
  })
})
