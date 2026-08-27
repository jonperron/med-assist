import type {
  AnalysisEvent,
  AnalysisResponse,
  FailureReason,
} from '../types/extraction'
import { EventStreamParser } from './serverSentEvents'

/**
 * Read `POST /api/analyze/stream`.
 *
 * The endpoint does the same work as `POST /api/analyze` and answers the same
 * body; what it adds is the half minute before it. A `batch` event fixes the
 * count, one `document` event lands as each file is read, and a `result` event
 * carries the answer.
 *
 * It is read with `fetch` rather than `EventSource`: the documents travel in
 * the request body, and `EventSource` only issues GETs.
 *
 * Nothing here is stored. The progress events carry a position and a boolean,
 * and the result is held in page state exactly as the plain endpoint's answer
 * was.
 */

/** Why a streamed analysis ended without a summary. */
export type StreamFailure = FailureReason | 'transport'

export class AnalysisStreamError extends Error {
  readonly reason: StreamFailure

  constructor(message: string, reason: StreamFailure) {
    super(message)
    this.name = 'AnalysisStreamError'
    this.reason = reason
  }
}

export interface StreamHandlers {
  /** How many documents the batch was accepted with. */
  onBatch?: (total: number) => void
  /** One document finished, at the position it was submitted at. */
  onDocument?: (index: number, read: boolean) => void
}

/** A refusal that arrived before the stream opened, as JSON. */
const REFUSAL_SHAPE = 'detail'

// Same ceiling as the axios path: a refusal is rendered as Med-Assist's own
// wording, so an upstream string of any length would read as something this
// app said.
const MAX_MESSAGE_LENGTH = 300

function usable(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.trim().length > 0 &&
    value.length <= MAX_MESSAGE_LENGTH
  )
}

/**
 * Read the message out of a refusal sent before the stream opened.
 *
 * Validation and model readiness are settled as dependencies, so a rejected
 * file type, an oversized batch and an unloaded model still answer 400, 413
 * and 503 as ordinary JSON with no events at all.
 */
async function refusalMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (typeof body !== 'object' || body === null) return fallback

    const detail = (body as Record<string, unknown>)[REFUSAL_SHAPE]
    const candidate =
      typeof detail === 'object' && detail !== null
        ? (detail as Record<string, unknown>).message
        : undefined

    return usable(candidate) ? candidate : fallback
  } catch {
    // An HTML error page from a proxy, or a body that ended early.
    return fallback
  }
}

/** Narrow a parsed payload to an event this client knows what to do with. */
function asEvent(payload: string): AnalysisEvent | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(payload)
  } catch {
    return null
  }

  if (typeof parsed !== 'object' || parsed === null) return null

  const stage = (parsed as Record<string, unknown>).stage
  if (
    stage !== 'batch' &&
    stage !== 'document' &&
    stage !== 'result' &&
    stage !== 'error'
  ) {
    // A stage this build has never heard of is skipped rather than guessed
    // at. The union is meant to grow, and an older client must keep working.
    return null
  }

  return parsed as AnalysisEvent
}

function handle(
  event: AnalysisEvent,
  handlers: StreamHandlers
): AnalysisResponse | null {
  switch (event.stage) {
    case 'batch':
      handlers.onBatch?.(event.total)
      return null
    case 'document':
      handlers.onDocument?.(event.index, event.read)
      return null
    case 'error':
      throw new AnalysisStreamError(event.message, event.reason)
    case 'result':
      return event.result
  }
}

/**
 * Stream one analysis, reporting each document as it lands.
 *
 * @throws AnalysisStreamError when the batch ends without a summary. `reason`
 * tells `unreadable_batch` - the clinician's documents - from `server_error`
 * and from a `transport` failure this client could not read at all, which are
 * three different things to say to a clinician.
 */
export async function streamAnalysis(
  url: string,
  files: File[],
  handlers: StreamHandlers,
  fallbackMessage: string,
  signal?: AbortSignal
): Promise<AnalysisResponse> {
  const body = new FormData()
  // One field name repeated per file: what FastAPI reads as List[UploadFile].
  files.forEach(file => body.append('files', file))

  const response = await fetch(url, { method: 'POST', body, signal })

  if (!response.ok) {
    throw new AnalysisStreamError(
      await refusalMessage(response, fallbackMessage),
      response.status >= 500 ? 'server_error' : 'unreadable_batch'
    )
  }

  if (!response.body) {
    throw new AnalysisStreamError(fallbackMessage, 'transport')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = new EventStreamParser()
  let result: AnalysisResponse | null = null

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      for (const payload of parser.push(decoder.decode(value, { stream: true }))) {
        const event = asEvent(payload)
        if (!event) continue

        result = handle(event, handlers) ?? result
      }
    }
  } finally {
    // Releases the lock whichever way the loop left, including the throw an
    // `error` event raises out of `handle`.
    reader.releaseLock()
  }

  if (!result) {
    // The stream ended without answering: a dropped connection, or a body
    // that is not ours. Either way there is no summary to show.
    throw new AnalysisStreamError(fallbackMessage, 'transport')
  }

  return result
}
