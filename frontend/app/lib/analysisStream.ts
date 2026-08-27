import type {
  AnalysisEvent,
  AnalysisResponse,
  FailureReason,
} from '../types/extraction'
import { MAX_FILES } from './documentSelection'
import { stripInvisible } from './documentName'
import { EventStreamParser, ParsedFrameTooLarge } from './serverSentEvents'

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

/**
 * Why a streamed analysis ended without a summary.
 *
 * `FailureReason` is what the stream itself can say. `too_large` and
 * `transport` are refusals that never reach an event: a batch the server sized
 * out before reading it, and an answer that did not arrive at all.
 */
export type StreamFailure = FailureReason | 'too_large' | 'transport'

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

// A refusal is rendered as Med-Assist's own wording, so an upstream string of
// any length would read as something this app said. The backend's messages are
// all short fixed constants; anything longer is not one of them.
const MAX_MESSAGE_LENGTH = 300

function usable(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.trim().length > 0 &&
    value.length <= MAX_MESSAGE_LENGTH
  )
}

/**
 * Make an upstream message safe to put in front of a clinician, or refuse it.
 *
 * Both paths a message can arrive by - the JSON refusal sent before the stream
 * opens, and the `error` event sent after - go through here, so the two cannot
 * drift. Invisible formatting characters are stripped for the same reason
 * `displayFilename` strips them: they let a string display as something other
 * than what it is, and this one is rendered as the application speaking.
 */
function safeMessage(value: unknown, fallback: string): string {
  if (!usable(value)) return fallback

  // Stripped, not truncated. Borrowing `displayFilename` would cut a message
  // between 120 and 300 characters mid-sentence and still render it as this
  // app's own wording - neither shown whole nor replaced by the fallback.
  const cleaned = stripInvisible(value)
  return cleaned.length > 0 ? cleaned : fallback
}

// A batch cannot hold more documents than the interface will select, so a
// larger count is not a batch this page posted. Nor can it hold none: the
// route refuses an empty batch with a 400, and a zero would leave the progress
// card reading "0 sur 0" with every later event out of bounds.
function acceptableTotal(total: unknown): total is number {
  return (
    Number.isInteger(total) && (total as number) >= 1 && (total as number) <= MAX_FILES
  )
}

// The closed set the stream can end on, typed against the generated schema so
// a member added to `FailureReason` shows up here as a type error rather than
// as a value this predicate silently downgrades.
const STREAM_REASONS: readonly FailureReason[] = ['unreadable_batch', 'server_error']

// `reason` is read off the wire and then picks what the clinician is told, so
// an unknown value must not reach the lookup that does it.
function acceptableReason(reason: unknown): reason is FailureReason {
  return STREAM_REASONS.includes(reason as FailureReason)
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

    return safeMessage(candidate, fallback)
  } catch {
    // An HTML error page from a proxy, or a body that ended early.
    return fallback
  }
}

/**
 * Which failure a status sent before the stream opened is.
 *
 * Only 400 is the clinician's scans: it is the refusal the route documents for
 * a batch nothing could be read from. 413 is their selection rather than their
 * scans - too many files, or one too large - and gets its own wording, because
 * "no summary could be established" over a size limit invites a retry of the
 * identical batch. A 5xx is the service. Everything else - a 404 from a
 * deployment older than the streaming route, a proxy's 405, a 429 - is
 * neither, and blaming a clinician's documents for a routing problem sends
 * them back to a scanner that will not fix it.
 */
function failureOf(status: number): StreamFailure {
  if (status === 400) return 'unreadable_batch'
  if (status === 413) return 'too_large'
  if (status >= 500) return 'server_error'
  return 'transport'
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
  handlers: StreamHandlers,
  fallbackMessage: string
): AnalysisResponse | null {
  switch (event.stage) {
    case 'batch':
      // A total this batch cannot have is not one this page posted. Skipping
      // the event leaves the count the selection already established.
      if (acceptableTotal(event.total)) handlers.onBatch?.(event.total)
      return null
    case 'document':
      handlers.onDocument?.(event.index, event.read)
      return null
    case 'error':
      throw new AnalysisStreamError(
        safeMessage(event.message, fallbackMessage),
        // An unknown reason is the service's own failure as far as this client
        // can tell. It must not read as the clinician's documents being at
        // fault, and it must not reach the headline lookup unrecognised.
        acceptableReason(event.reason) ? event.reason : 'server_error'
      )
    case 'result':
      // Checked here rather than trusted: `asEvent` narrows the tag, not the
      // payload behind it, and everything downstream indexes `documents`.
      return isAnalysisResponse(event.result) ? event.result : null
  }
}

/** The shape every screen behind a finished analysis indexes into. */
function isAnalysisResponse(result: unknown): result is AnalysisResponse {
  if (typeof result !== 'object' || result === null) return false

  const body = result as Record<string, unknown>
  const summary = body.summary

  return (
    typeof summary === 'object' &&
    summary !== null &&
    Array.isArray((summary as Record<string, unknown>).sections) &&
    Array.isArray(body.documents)
  )
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
      failureOf(response.status)
    )
  }

  if (!response.body) {
    throw new AnalysisStreamError(fallbackMessage, 'transport')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = new EventStreamParser()
  let result: AnalysisResponse | null = null
  let finished = false

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) {
        finished = true
        break
      }

      let payloads: string[]
      try {
        payloads = parser.push(decoder.decode(value, { stream: true }))
      } catch (error: unknown) {
        // The parser gave up on a body that is not this stream. Re-raised as
        // this module's own error so every caller gets a `reason`, which is
        // what the signature promises.
        if (error instanceof ParsedFrameTooLarge) {
          throw new AnalysisStreamError(fallbackMessage, 'transport')
        }
        throw error
      }

      for (const payload of payloads) {
        const event = asEvent(payload)
        if (!event) continue

        result = handle(event, handlers, fallbackMessage) ?? result
      }
    }
  } finally {
    // An `error` event throws out of `handle`, and a frame past the parser's
    // cap throws out of `push`. Both leave a body still arriving, so it is
    // cancelled rather than left to be collected - on a local deployment that
    // is a connection the backend is still writing to.
    if (!finished) await reader.cancel().catch(() => {})
    reader.releaseLock()
  }

  if (!result) {
    // The stream ended without answering: a dropped connection, or a body
    // that is not ours. Either way there is no summary to show.
    throw new AnalysisStreamError(fallbackMessage, 'transport')
  }

  return result
}
