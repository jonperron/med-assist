import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import HomePage from '../page'
import type { AnalysisResponse } from '../types/extraction'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

const RESULT: AnalysisResponse = {
  summary: {
    patient: 'Patient, 67 ans, homme.',
    sections: [
      {
        key: 'symptoms',
        heading: 'Signes et symptômes',
        sentence: 'Fièvre.',
        findings: [{ text: 'fièvre', documents: [0] }],
      },
    ],
    document_count: 1,
    date_range: null,
    empty: false,
  },
  documents: [],
  retained: false,
}

function frame(event: unknown): string {
  return `data: ${JSON.stringify(event)}\n\n`
}

/** A finished stream: the batch, one event per document, then the result. */
function stream(
  { total = 1, read = [true], result = RESULT } = {} as {
    total?: number
    read?: boolean[]
    result?: AnalysisResponse
  }
): string {
  return [
    frame({ stage: 'batch', total }),
    ...read.map((wasRead, index) =>
      frame({
        stage: 'document',
        index,
        read: wasRead,
        unreadable_reason: wasRead ? null : 'no_text',
      })
    ),
    frame({ stage: 'result', result }),
  ].join('')
}

/** A `Response` whose body yields `chunks` in order. */
function streaming(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder()
  return {
    ok: status < 400,
    status,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
        controller.close()
      },
    }),
  } as unknown as Response
}

/** A refusal sent before the stream opened, as ordinary JSON. */
function refusal(status: number, message: string): Response {
  return {
    ok: false,
    status,
    json: async () => ({ detail: { message } }),
  } as unknown as Response
}

function answers(chunks: string[] = [stream()]) {
  fetchMock.mockResolvedValue(streaming(chunks))
}

function selectFiles(count = 1, type = 'text/plain', extension = 'txt') {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const files = Array.from(
    { length: count },
    (_, index) => new File(['content'], `report${index}.${extension}`, { type })
  )
  fireEvent.change(input, { target: { files } })
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: /^Résumer / }))
}

function postedForm(call = 0) {
  return (fetchMock.mock.calls[call][1] as RequestInit).body as FormData
}

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('summarises the selected documents', async () => {
    answers()

    render(<HomePage />)
    selectFiles()
    submit()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(fetchMock.mock.calls[0][0]).toContain('/api/analyze/stream')
    expect(await screen.findByText('fièvre')).toBeInTheDocument()
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('asks the backend nothing until the clinician submits', () => {
    render(<HomePage />)
    selectFiles(2)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('2 documents prêts')).toBeInTheDocument()
  })

  it('posts every document under the field the API reads', async () => {
    answers()

    render(<HomePage />)
    selectFiles(3)
    submit()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(3)
  })

  it('refuses an unsupported document without asking the backend', () => {
    render(<HomePage />)
    selectFiles(1, 'image/png', 'png')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/PDF, DOCX ou TXT/)
    expect(screen.queryByRole('button', { name: /^Résumer / })).not.toBeInTheDocument()
  })

  it('distinguishes a format the browser could not name from a wrong one', () => {
    render(<HomePage />)
    selectFiles(1, 'application/octet-stream', 'docx')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/navigateur/)
  })

  it('drops a document from the batch before submitting', async () => {
    answers()

    render(<HomePage />)
    selectFiles(2)
    fireEvent.click(screen.getByRole('button', { name: 'Retirer report0.txt' }))
    submit()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(1)
  })

  it('never stores and never issues an id', async () => {
    answers()

    render(<HomePage />)
    selectFiles()
    submit()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce())
    expect(fetchMock.mock.calls[0][0]).not.toContain('/api/upload')
    expect(screen.queryByText(/File ID/)).not.toBeInTheDocument()
  })

  it('offers no storage, retention or masking controls', () => {
    render(<HomePage />)

    // The clinician is asked for documents, not for a data-handling policy.
    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
    expect(screen.queryByText(/serveur|supprim|masqu/i)).not.toBeInTheDocument()
  })

  it('counts the documents off as the stream reports them', async () => {
    // The batch and the first document land, and the result is held back, so
    // the progress card is what is on screen.
    const chunks = [
      frame({ stage: 'batch', total: 3 }),
      frame({ stage: 'document', index: 0, read: true, unreadable_reason: null }),
    ]
    let release: () => void = () => {}
    const held = new Promise<void>(resolve => (release = resolve))

    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        async start(controller) {
          const encoder = new TextEncoder()
          chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
          await held
          controller.enqueue(
            encoder.encode(
              [
                frame({
                  stage: 'document',
                  index: 1,
                  read: true,
                  unreadable_reason: null,
                }),
                frame({
                  stage: 'document',
                  index: 2,
                  read: true,
                  unreadable_reason: null,
                }),
                frame({ stage: 'result', result: RESULT }),
              ].join('')
            )
          )
          controller.close()
        },
      }),
    } as unknown as Response)

    render(<HomePage />)
    selectFiles(3)
    submit()

    expect(await screen.findByText('1 sur 3')).toBeInTheDocument()

    release()
    expect(await screen.findByText('fièvre')).toBeInTheDocument()
  })

  it('shows progress while the analysis runs', async () => {
    let settle: (value: Response) => void = () => {}
    fetchMock.mockReturnValue(new Promise<Response>(resolve => (settle = resolve)))

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByText(/Lecture du document/)).toBeInTheDocument()

    settle(streaming([stream()]))
    await waitFor(() =>
      expect(screen.queryByText(/Lecture du document/)).not.toBeInTheDocument()
    )
  })

  it('marks a document the stream reported unread while it is still reading', async () => {
    const chunks = [
      frame({ stage: 'batch', total: 2 }),
      frame({ stage: 'document', index: 0, read: false, unreadable_reason: 'no_text' }),
    ]
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          const encoder = new TextEncoder()
          chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
          // Left open: the progress card stays on screen.
        },
      }),
    } as unknown as Response)

    render(<HomePage />)
    selectFiles(2)
    submit()

    const card = await screen.findByRole('status')
    expect(within(card).getByText('non lu')).toBeInTheDocument()
  })

  it('surfaces the message of a refusal sent before the stream opened', async () => {
    fetchMock.mockResolvedValue(
      refusal(400, 'Unable to extract text from the document.')
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to extract text from the document.'
    )
  })

  it('tells a batch that could not be read from a service that failed', async () => {
    fetchMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({
          stage: 'error',
          reason: 'unreadable_batch',
          message: 'Unable to extract text from the document.',
        }),
      ])
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Aucun résumé n'a pu être établi"
    )
  })

  it('does not blame the documents for the service failing', async () => {
    fetchMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({
          stage: 'error',
          reason: 'server_error',
          message: 'Internal server error',
        }),
      ])
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse n'a pas abouti"
    )
  })

  it('reports a stream that ended without answering', async () => {
    fetchMock.mockResolvedValue(streaming([frame({ stage: 'batch', total: 1 })]))

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse s'est interrompue"
    )
  })

  it('reports a network failure without implicating the documents', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse s'est interrompue"
    )
  })

  it('keeps the batch so a failed analysis can be retried', async () => {
    fetchMock.mockResolvedValue(refusal(500, 'Internal server error'))

    render(<HomePage />)
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    answers()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(postedForm(1).getAll('files')).toHaveLength(2)
  })

  it('drops the failure card when the batch it described is emptied', async () => {
    fetchMock.mockResolvedValue(refusal(500, 'Internal server error'))

    render(<HomePage />)
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    fireEvent.click(screen.getByRole('button', { name: 'Tout retirer' }))

    // A retry against an empty batch would be a control that does nothing.
    expect(screen.queryByRole('button', { name: 'Réessayer' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('drops the failure card when the batch is changed', async () => {
    fetchMock.mockResolvedValue(refusal(500, 'Internal server error'))

    render(<HomePage />)
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    fireEvent.click(screen.getByRole('button', { name: 'Retirer report0.txt' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reports a result event that does not carry a summary', async () => {
    fetchMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({ stage: 'result', result: { detail: 'not ours' } }),
      ])
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText(/Résumé de/)).not.toBeInTheDocument()
  })

  it('reports a summary whose sections are not a list', async () => {
    fetchMock.mockResolvedValue(
      streaming([
        frame({
          stage: 'result',
          result: { summary: { document_count: 1, empty: false, sections: null } },
        }),
      ])
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('ignores an event stage this build has never heard of', async () => {
    // The union is meant to grow. An older client has to keep working.
    fetchMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({ stage: 'weather', forecast: 'rain' }),
        'data: not json at all\n\n',
        frame({ stage: 'result', result: RESULT }),
      ])
    )

    render(<HomePage />)
    selectFiles()
    submit()

    expect(await screen.findByText('fièvre')).toBeInTheDocument()
  })

  it('refuses an oversized document without asking the backend', () => {
    render(<HomePage />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const heavy = new File(['x'], 'gros.txt', { type: 'text/plain' })
    Object.defineProperty(heavy, 'size', { value: 11 * 1024 * 1024 })
    fireEvent.change(input, { target: { files: [heavy] } })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/volumineux/)
  })

  it('clears a previous summary when starting over', async () => {
    answers()

    render(<HomePage />)
    selectFiles()
    submit()
    expect(await screen.findByText('fièvre')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Nouveau résumé' }))

    await waitFor(() => expect(screen.queryByText('fièvre')).not.toBeInTheDocument())
    expect(screen.queryByText(/documents prêts/)).not.toBeInTheDocument()
  })
})
