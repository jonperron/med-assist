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

  it('passes the abort signal through to fetch', async () => {
    fetchMock.mockResolvedValue(streaming(frame({ stage: 'result', result: RESULT })))
    const controller = new AbortController()

    await run({}, controller.signal)

    expect((fetchMock.mock.calls[0][1] as RequestInit).signal).toBe(controller.signal)
  })
})
