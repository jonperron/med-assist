import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import HomePage from '../page'
import { READY_PATH } from '../lib/serviceStatus'
import type { AnalysisResponse } from '../types/extraction'

// The page makes two different requests, and every test cares about exactly one
// of them: the readiness check the poll issues on mount, and the analysis the
// clinician submits. Routed apart here so a test can set one without setting
// the other, and so a call index means what it used to.
const analysisMock = vi.fn()
const readyMock = vi.fn()

function route(url: string, init?: RequestInit) {
  return String(url).endsWith(READY_PATH) ? readyMock(url, init) : analysisMock(url, init)
}

const fetchMock = vi.fn(route)
vi.stubGlobal('fetch', fetchMock)

/** A backend with the model in memory. The default every test starts from. */
function ready(): Response {
  return { ok: true, status: 200 } as unknown as Response
}

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
  analysisMock.mockResolvedValue(streaming(chunks))
}

/**
 * Render the page and let the readiness check on mount settle.
 *
 * The check is issued from an effect and resolves on a microtask, so without
 * flushing it here the state it sets lands outside `act` and every test that
 * does not await something else warns about it.
 */
async function renderPage() {
  let rendered!: ReturnType<typeof render>
  await act(async () => {
    rendered = render(<HomePage />)
  })
  return rendered
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

/**
 * The service notice, selected by name.
 *
 * Four components on these screens are `role="status"`, and an unqualified
 * query throws on more than one match - a coupling that would otherwise only
 * show up as two unrelated tests breaking on a layout change.
 */
function notice() {
  return screen.getByRole('status', { name: 'État du service' })
}

function queryNotice() {
  return screen.queryByRole('status', { name: 'État du service' })
}

function postedForm(call = 0) {
  return (analysisMock.mock.calls[call][1] as RequestInit).body as FormData
}

describe('HomePage', () => {
  beforeEach(() => {
    // Reset rather than clear. `clearAllMocks` drops call history but leaves
    // implementations in place, so an analysis response set by one test would
    // still be answering in the next test that forgot to set its own - which
    // passes, on the previous test's stream.
    vi.resetAllMocks()
    fetchMock.mockImplementation(route)
    readyMock.mockResolvedValue(ready())
  })

  it('summarises the selected documents', async () => {
    answers()

    await renderPage()
    selectFiles()
    submit()

    await waitFor(() => expect(analysisMock).toHaveBeenCalledOnce())
    expect(analysisMock.mock.calls[0][0]).toContain('/api/analyze/stream')
    expect(await screen.findByText('fièvre')).toBeInTheDocument()
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('asks the backend nothing until the clinician submits', async () => {
    await renderPage()
    selectFiles(2)

    expect(analysisMock).not.toHaveBeenCalled()
    expect(screen.getByText('2 documents prêts')).toBeInTheDocument()
  })

  it('posts every document under the field the API reads', async () => {
    answers()

    await renderPage()
    selectFiles(3)
    submit()

    await waitFor(() => expect(analysisMock).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(3)
  })

  it('refuses an unsupported document without asking the backend', async () => {
    await renderPage()
    selectFiles(1, 'image/png', 'png')

    expect(analysisMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/PDF, DOCX ou TXT/)
    expect(screen.queryByRole('button', { name: /^Résumer / })).not.toBeInTheDocument()
  })

  it('distinguishes a format the browser could not name from a wrong one', async () => {
    await renderPage()
    selectFiles(1, 'application/octet-stream', 'docx')

    expect(analysisMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/navigateur/)
  })

  it('drops a document from the batch before submitting', async () => {
    answers()

    await renderPage()
    selectFiles(2)
    fireEvent.click(screen.getByRole('button', { name: 'Retirer report0.txt' }))
    submit()

    await waitFor(() => expect(analysisMock).toHaveBeenCalledOnce())
    expect(postedForm().getAll('files')).toHaveLength(1)
  })

  it('never stores and never issues an id', async () => {
    answers()

    await renderPage()
    selectFiles()
    submit()

    await waitFor(() => expect(analysisMock).toHaveBeenCalledOnce())
    expect(analysisMock.mock.calls[0][0]).not.toContain('/api/upload')
    expect(screen.queryByText(/File ID/)).not.toBeInTheDocument()
  })

  it('offers no storage, retention or masking controls', async () => {
    await renderPage()

    // The clinician is asked for documents, not for a data-handling policy.
    // The ban on the vocabulary is the original guard, now scoped to `main`
    // rather than dropped: the footer states what becomes of the documents,
    // which is a fact about the service and belongs on screen, and scoping
    // exempts it by construction instead of by deleting the assertion. Inside
    // the working area the words still have no business appearing, because
    // there is no choice to offer and a control would imply one.
    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
    expect(document.querySelectorAll('input[type="radio"]')).toHaveLength(0)
    expect(document.querySelectorAll('select')).toHaveLength(0)

    const workingArea = within(screen.getByRole('main'))
    expect(workingArea.queryByText(/serveur|supprim|masqu/i)).not.toBeInTheDocument()
  })

  it('makes no absolute claim about erasure anywhere on the page', () => {
    render(<HomePage />)

    // What the footer may say is bounded by what the service does. The spool
    // the HTTP server writes for a large part is a real file - RAM-backed
    // under `docker-compose.yml`, not necessarily anywhere else - so "never
    // written to disk" and "definitively deleted" are both stronger than the
    // truth. This guards the whole page, footer included.
    expect(document.body.textContent).not.toMatch(/jamais.{0,30}disque/i)
    expect(document.body.textContent).not.toMatch(/définitivement/i)
  })

  it('carries the footer', () => {
    render(<HomePage />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(
      /Aucun document n'est enregistré sur le serveur/
    )
    expect(
      screen.getByRole('link', { name: /Signaler un problème/ })
    ).toBeInTheDocument()
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

    analysisMock.mockResolvedValue({
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

    await renderPage()
    selectFiles(3)
    submit()

    expect(await screen.findByText('1 sur 3')).toBeInTheDocument()

    release()
    expect(await screen.findByText('fièvre')).toBeInTheDocument()
  })

  it('shows progress while the analysis runs', async () => {
    let settle: (value: Response) => void = () => {}
    analysisMock.mockReturnValue(new Promise<Response>(resolve => (settle = resolve)))

    await renderPage()
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
    analysisMock.mockResolvedValue({
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

    await renderPage()
    selectFiles(2)
    submit()

    // The card appears on the batch frame, and the mark only on the document
    // frame that follows it a tick later. Waiting for the card and then reading
    // it synchronously asserts on the state in between.
    const card = await screen.findByRole('status')
    expect(await within(card).findByText('non lu')).toBeInTheDocument()
  })

  it('surfaces the message of a refusal sent before the stream opened', async () => {
    analysisMock.mockResolvedValue(
      refusal(400, 'Unable to extract text from the document.')
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to extract text from the document.'
    )
  })

  it('tells a batch that could not be read from a service that failed', async () => {
    analysisMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({
          stage: 'error',
          reason: 'unreadable_batch',
          message: 'Unable to extract text from the document.',
        }),
      ])
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Aucun résumé n'a pu être établi"
    )
  })

  it('does not blame the documents for the service failing', async () => {
    analysisMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({
          stage: 'error',
          reason: 'server_error',
          message: 'Internal server error',
        }),
      ])
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse n'a pas abouti"
    )
  })

  it('reports a stream that ended without answering', async () => {
    analysisMock.mockResolvedValue(streaming([frame({ stage: 'batch', total: 1 })]))

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse s'est interrompue"
    )
  })

  it('reports a network failure without implicating the documents', async () => {
    analysisMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse s'est interrompue"
    )
  })

  it('keeps the batch so a failed analysis can be retried', async () => {
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    answers()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => expect(analysisMock).toHaveBeenCalledTimes(2))
    expect(postedForm(1).getAll('files')).toHaveLength(2)
  })

  it('starts over from a failed analysis rather than only retrying the same batch', async () => {
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    fireEvent.click(screen.getByRole('button', { name: "Choisir d'autres documents" }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(/documents prêts/)).not.toBeInTheDocument()
    expect(document.querySelector('input[type="file"]')).toBeInTheDocument()
  })

  it('drops the failure card when the batch it described is emptied', async () => {
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    fireEvent.click(screen.getByRole('button', { name: 'Tout retirer' }))

    // A retry against an empty batch would be a control that does nothing.
    expect(screen.queryByRole('button', { name: 'Réessayer' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('drops the failure card when the batch is changed', async () => {
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    fireEvent.click(screen.getByRole('button', { name: 'Retirer report0.txt' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reports a result event that does not carry a summary', async () => {
    analysisMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({ stage: 'result', result: { detail: 'not ours' } }),
      ])
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText(/Résumé de/)).not.toBeInTheDocument()
  })

  it('reports a summary whose sections are not a list', async () => {
    analysisMock.mockResolvedValue(
      streaming([
        frame({
          stage: 'result',
          result: { summary: { document_count: 1, empty: false, sections: null } },
        }),
      ])
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('ignores an event stage this build has never heard of', async () => {
    // The union is meant to grow. An older client has to keep working.
    analysisMock.mockResolvedValue(
      streaming([
        frame({ stage: 'batch', total: 1 }),
        frame({ stage: 'weather', forecast: 'rain' }),
        'data: not json at all\n\n',
        frame({ stage: 'result', result: RESULT }),
      ])
    )

    await renderPage()
    selectFiles()
    submit()

    expect(await screen.findByText('fièvre')).toBeInTheDocument()
  })

  it('refuses an oversized document without asking the backend', async () => {
    await renderPage()

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const heavy = new File(['x'], 'gros.txt', { type: 'text/plain' })
    Object.defineProperty(heavy, 'size', { value: 11 * 1024 * 1024 })
    fireEvent.change(input, { target: { files: [heavy] } })

    expect(analysisMock).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/volumineux/)
  })

  it('clears a previous summary when starting over', async () => {
    answers()

    await renderPage()
    selectFiles()
    submit()
    expect(await screen.findByText('fièvre')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Nouveau résumé' }))

    await waitFor(() => expect(screen.queryByText('fièvre')).not.toBeInTheDocument())
    expect(screen.queryByText(/documents prêts/)).not.toBeInTheDocument()
  })

  it('warns before the clinician commits anything when the service cannot analyse', async () => {
    readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))

    await renderPage()

    // No document selected, nothing submitted: the state of the service is on
    // screen before the clinician gathers a batch it would have refused.
    expect(notice()).toHaveTextContent("Le service n'est pas disponible")
    expect(analysisMock).not.toHaveBeenCalled()
  })

  it('says nothing about the service while the first check is still open', async () => {
    // A warning rendered during the first round trip would flash on every load
    // of a perfectly healthy deployment.
    readyMock.mockReturnValue(new Promise<Response>(() => {}))

    // Rendered directly rather than through `renderPage`: the point is the
    // window before the first answer, so there is deliberately nothing to
    // flush and the promise never settles.
    render(<HomePage />)

    expect(queryNotice()).not.toBeInTheDocument()
    // And the interface is not held shut while it waits to hear.
    selectFiles()
    expect(screen.getByRole('button', { name: /^Résumer / })).toBeEnabled()
  })

  it('holds the analysis shut rather than sending a batch that comes back refused', async () => {
    readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))

    await renderPage()
    selectFiles(2)

    expect(screen.getByRole('button', { name: /^Résumer / })).toBeDisabled()

    submit()
    expect(analysisMock).not.toHaveBeenCalled()
  })

  it('lets the clinician gather documents while the service is down', async () => {
    // The wait is usually seconds. Locking the dropzone would make them redo
    // the selection once it clears.
    readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))

    await renderPage()
    selectFiles(2)

    expect(screen.getByText('2 documents prêts')).toBeInTheDocument()
  })

  it('clears the warning by itself once the service comes up', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      readyMock
        .mockResolvedValueOnce(refusal(503, 'The service is starting up.'))
        .mockResolvedValue(ready())

      await renderPage()
      selectFiles()
      expect(notice()).toHaveTextContent("Le service n'est pas disponible")
      expect(screen.getByRole('button', { name: /^Résumer / })).toBeDisabled()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000)
      })

      // No reload, no second visit: the poll re-enables the interface.
      expect(queryNotice()).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^Résumer / })).toBeEnabled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('raises the warning when a service that was up goes away', async () => {
    // The recovery path is tested below; this is the other direction, and it is
    // the one that covers the reschedule after a ready answer. Without it, a
    // regression that stops polling once ready passes the whole suite.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      await renderPage()
      selectFiles()
      expect(queryNotice()).not.toBeInTheDocument()

      readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000)
      })

      expect(notice()).toHaveTextContent("Le service n'est pas disponible")
      expect(screen.getByRole('button', { name: /^Résumer / })).toBeDisabled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('reports a check it could not reach without taking the analysis away', async () => {
    // A deployment that does not route /readyz would otherwise have a working
    // analysis path permanently disabled by a probe that does not work.
    readyMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await renderPage()
    selectFiles()

    expect(notice()).toHaveTextContent('Med-Assist ne répond pas')
    expect(screen.getByRole('button', { name: /^Résumer / })).toBeEnabled()
  })

  it('takes the retry away once the service turns out to be refusing', async () => {
    // The state where the gate matters most: the previous attempt just failed
    // and the service is known to be refusing. An enabled retry beside a
    // disabled submit button is the interface contradicting itself.
    //
    // The service is up when the batch is submitted - otherwise the submit
    // button is already shut and no failure card is ever reached, which would
    // make this pass without exercising anything. It goes down in time for the
    // re-check that the failure itself triggers.
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))
    submit()

    // The failure card is on screen, so the retry is a control this state would
    // otherwise be offering.
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "L'analyse n'a pas abouti"
    )
    await waitFor(() => expect(queryNotice()).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Réessayer' })).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: "Choisir d'autres documents" })
    ).toBeInTheDocument()
  })

  it('keeps the retry while the service is up', async () => {
    // The guard against the test above passing for the wrong reason: the same
    // failure with a healthy service must still offer the retry.
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    selectFiles(2)
    submit()
    await screen.findByRole('alert')

    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })

  it('asks the service about itself as soon as an analysis fails', async () => {
    // The failed request already carries an answer about the service. Waiting
    // up to 30 seconds for the next scheduled poll would leave the button
    // enabled for a second doomed attempt.
    analysisMock.mockResolvedValue(refusal(500, 'Internal server error'))

    await renderPage()
    const beforeSubmit = readyMock.mock.calls.length

    selectFiles()
    submit()
    await screen.findByRole('alert')

    await waitFor(() =>
      expect(readyMock.mock.calls.length).toBeGreaterThan(beforeSubmit)
    )
  })

  it('does not go and ask when it was the documents that failed', async () => {
    // A batch nothing could be read from says nothing about the service.
    analysisMock.mockResolvedValue(
      refusal(400, 'Unable to extract text from the document.')
    )

    await renderPage()
    const beforeSubmit = readyMock.mock.calls.length

    selectFiles()
    submit()
    await screen.findByRole('alert')

    expect(readyMock.mock.calls.length).toBe(beforeSubmit)
  })

  it('checks again when the clinician comes back to the tab', async () => {
    // A hidden tab has its timers throttled to roughly a minute, so the promise
    // that the screen updates by itself needs help on return.
    readyMock.mockResolvedValue(refusal(503, 'The service is starting up.'))
    await renderPage()
    const beforeReturn = readyMock.mock.calls.length

    readyMock.mockResolvedValue(ready())
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(readyMock.mock.calls.length).toBeGreaterThan(beforeReturn)
    expect(queryNotice()).not.toBeInTheDocument()
  })

  it('stops checking once the page is left', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { unmount } = await renderPage()
      const checked = readyMock.mock.calls.length

      unmount()
      await act(async () => {
        await vi.advanceTimersByTimeAsync(120_000)
      })

      expect(readyMock).toHaveBeenCalledTimes(checked)
    } finally {
      vi.useRealTimers()
    }
  })

  it('abandons the in-flight request rather than leaving it running when the page is left', async () => {
    let capturedSignal: AbortSignal | undefined
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(encoder.encode(frame({ stage: 'batch', total: 1 })))
        // Left open on purpose: nothing here closes it, the way a request
        // genuinely still in flight would look from the caller's side.
      },
    })

    analysisMock.mockImplementation((_: string, init: RequestInit) => {
      capturedSignal = init.signal as AbortSignal
      return Promise.resolve({ ok: true, status: 200, body } as unknown as Response)
    })

    const { unmount } = await renderPage()
    selectFiles()
    submit()

    await screen.findByText(/Lecture du document/)
    expect(capturedSignal?.aborted).toBe(false)

    unmount()

    expect(capturedSignal?.aborted).toBe(true)
  })
})
