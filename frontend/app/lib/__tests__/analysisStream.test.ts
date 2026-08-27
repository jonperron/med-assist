import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisStreamError, streamAnalysis } from '../analysisStream'
import type { AnalysisResponse } from '../../types/extraction'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

const FALLBACK = "Échec de l'analyse des documents."

const RESULT = {
  summary: {
    patient: null,
    sections: [],
    document_count: 1,
    date_range: null,
    empty: true,
  },
  documents: [],
  retained: false,
} as unknown as AnalysisResponse

function frame(event: unknown): string {
  return `data: ${JSON.stringify(event)}\n\n`
}

function streaming(body: string, status = 200): Response {
  const encoder = new TextEncoder()
  return {
    ok: status < 400,
    status,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(body))
        controller.close()
      },
    }),
  } as unknown as Response
}

function files(count = 1): File[] {
  return Array.from(
    { length: count },
    (_, index) => new File(['content'], `report${index}.txt`, { type: 'text/plain' })
  )
}

function run(handlers = {}, signal?: AbortSignal) {
  return streamAnalysis('/api/analyze/stream', files(), handlers, FALLBACK, signal)
}

describe('streamAnalysis', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts every document under the field the API reads', async () => {
    fetchMock.mockResolvedValue(streaming(frame({ stage: 'result', result: RESULT })))

    await streamAnalysis('/api/analyze/stream', files(3), {}, FALLBACK)

    const request = fetchMock.mock.calls[0][1] as RequestInit
    expect(request.method).toBe('POST')
    expect((request.body as FormData).getAll('files')).toHaveLength(3)
  })

  it('answers with the result the stream ended on', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        frame({ stage: 'batch', total: 1 }) + frame({ stage: 'result', result: RESULT })
      )
    )

    await expect(run()).resolves.toEqual(RESULT)
  })

  it('reports the batch and each document as they land', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        [
          frame({ stage: 'batch', total: 2 }),
          frame({ stage: 'document', index: 0, read: true, unreadable_reason: null }),
          frame({
            stage: 'document',
            index: 1,
            read: false,
            unreadable_reason: 'no_text',
          }),
          frame({ stage: 'result', result: RESULT }),
        ].join('')
      )
    )

    const onBatch = vi.fn()
    const onDocument = vi.fn()
    await run({ onBatch, onDocument })

    expect(onBatch).toHaveBeenCalledExactlyOnceWith(2)
    expect(onDocument.mock.calls).toEqual([
      [0, true],
      [1, false],
    ])
  })

  it('raises the reason of an error event rather than its wording', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        frame({
          stage: 'error',
          reason: 'unreadable_batch',
          message: 'Unable to extract text from the document.',
        })
      )
    )

    await expect(run()).rejects.toMatchObject({
      reason: 'unreadable_batch',
      message: 'Unable to extract text from the document.',
    })
  })

  it('reads the message of a refusal sent before the stream opened', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: { message: 'Invalid file type.' } }),
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({
      reason: 'unreadable_batch',
      message: 'Invalid file type.',
    })
  })

  it('calls a 500 before the stream a server error, not a bad document', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: { message: 'The model is still loading.' } }),
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({ reason: 'server_error' })
  })

  it('falls back rather than showing an upstream body it cannot read', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('<html>502 Bad Gateway</html>')
      },
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({ message: FALLBACK })
  })

  it('falls back rather than rendering a wall of upstream text', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: { message: 'x'.repeat(301) } }),
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({ message: FALLBACK })
  })

  it('falls back when the refusal body is not the documented shape', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: { message: { nested: true } } }),
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({ message: FALLBACK })
  })

  it('reports a stream that ended without a result', async () => {
    fetchMock.mockResolvedValue(streaming(frame({ stage: 'batch', total: 1 })))

    await expect(run()).rejects.toMatchObject({ reason: 'transport' })
  })

  it('reports a response with no body at all', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, body: null } as Response)

    await expect(run()).rejects.toBeInstanceOf(AnalysisStreamError)
  })

  it('skips a stage it has never heard of and an unparsable payload', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        [
          frame({ stage: 'weather', forecast: 'rain' }),
          'data: not json\n\n',
          'data: "a string"\n\n',
          frame({ stage: 'result', result: RESULT }),
        ].join('')
      )
    )

    await expect(run()).resolves.toEqual(RESULT)
  })

  it('holds an error event message to the same ceiling as a refusal', async () => {
    // The card renders this as Med-Assist's own wording, so a wall of
    // upstream text would read as something this app said.
    fetchMock.mockResolvedValue(
      streaming(
        frame({
          stage: 'error',
          reason: 'server_error',
          message: 'x'.repeat(301),
        })
      )
    )

    await expect(run()).rejects.toMatchObject({ message: FALLBACK })
  })

  it('strips invisible characters out of an error event message', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        frame({
          stage: 'error',
          reason: 'server_error',
          message: 'Erreur\u202einterne',
        })
      )
    )

    await expect(run()).rejects.toMatchObject({ message: 'Erreurinterne' })
  })

  it('calls a reason it has never heard of a server error', async () => {
    // It must not read as the clinician's documents being at fault, and it
    // must not reach the headline lookup unrecognised.
    fetchMock.mockResolvedValue(
      streaming(
        frame({ stage: 'error', reason: 'cosmic_rays', message: 'Something failed' })
      )
    )

    await expect(run()).rejects.toMatchObject({ reason: 'server_error' })
  })

  it('ignores a batch total no batch could have', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        [
          frame({ stage: 'batch', total: 1e9 }),
          frame({ stage: 'batch', total: -1 }),
          frame({ stage: 'batch', total: 'lots' }),
          frame({ stage: 'result', result: RESULT }),
        ].join('')
      )
    )

    const onBatch = vi.fn()
    await run({ onBatch })

    expect(onBatch).not.toHaveBeenCalled()
  })

  it('accepts a batch total the interface could have selected', async () => {
    fetchMock.mockResolvedValue(
      streaming(
        frame({ stage: 'batch', total: 3 }) + frame({ stage: 'result', result: RESULT })
      )
    )

    const onBatch = vi.fn()
    await run({ onBatch })

    expect(onBatch).toHaveBeenCalledExactlyOnceWith(3)
  })

  it('does not blame the documents for a route that is not there', async () => {
    // A deployment older than the streaming endpoint answers 404. Telling the
    // clinician no summary could be established would send them back to their
    // scanner over a routing problem.
    fetchMock.mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not Found' }),
    } as unknown as Response)

    await expect(run()).rejects.toMatchObject({ reason: 'transport' })
  })

  it("calls a 400 and a 413 the clinician's batch", async () => {
    for (const status of [400, 413]) {
      fetchMock.mockResolvedValue({
        ok: false,
        status,
        json: async () => ({ detail: { message: 'Refusé.' } }),
      } as unknown as Response)

      await expect(run()).rejects.toMatchObject({ reason: 'unreadable_batch' })
    }
  })

  it('refuses a result whose documents are not a list', async () => {
    // Every screen behind a finished analysis indexes into it.
    fetchMock.mockResolvedValue(
      streaming(
        frame({
          stage: 'result',
          result: { summary: { sections: [] }, documents: null },
        })
      )
    )

    await expect(run()).rejects.toMatchObject({ reason: 'transport' })
  })

  it('passes the abort signal through to fetch', async () => {
    fetchMock.mockResolvedValue(streaming(frame({ stage: 'result', result: RESULT })))
    const controller = new AbortController()

    await run({}, controller.signal)

    expect((fetchMock.mock.calls[0][1] as RequestInit).signal).toBe(controller.signal)
  })

  it('propagates an abort raised mid-stream rather than reporting it as a failure', async () => {
    // A body whose reader only errors once the caller's own signal fires, the
    // way a real fetch stream does. The caller (the page) tells an abort it
    // asked for apart from a failure by reading this signal itself, so
    // streamAnalysis must not repackage it as an AnalysisStreamError.
    let controller: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        controller = c
      },
    })

    const abortController = new AbortController()
    abortController.signal.addEventListener('abort', () => {
      controller.error(new DOMException('The user aborted a request.', 'AbortError'))
    })

    fetchMock.mockResolvedValue({ ok: true, status: 200, body } as unknown as Response)

    const pending = run({}, abortController.signal)
    // Swallow the rejection racing the abort so Node does not report it as
    // unhandled before the assertion below observes it.
    pending.catch(() => {})

    abortController.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not swallow a connection dropped mid-stream', async () => {
    // Distinct from a stream that simply closes with no result: this one
    // fails outright, and that must not be reported as a clean end either.
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(encoder.encode(frame({ stage: 'batch', total: 1 })))
        controller.error(new TypeError('network error'))
      },
    })

    fetchMock.mockResolvedValue({ ok: true, status: 200, body } as unknown as Response)

    await expect(run()).rejects.toThrow('network error')
  })
})
