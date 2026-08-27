/**
 * Split a `text/event-stream` body into the payload of each event.
 *
 * Only `data` is read: the analysis stream tags every event inside its own
 * JSON with `stage`, so the SSE `event:` field carries nothing this client
 * needs. Comment lines - a keep-alive is one - and any other field are
 * skipped rather than parsed.
 *
 * A frame is terminated by a blank line, and a multi-line `data` field is
 * joined with newlines, as the wire format specifies. The stream arrives in
 * arbitrary chunks, so the parser holds the tail of one until the rest of it
 * lands.
 */

/**
 * How much of an unfinished frame is held before the stream is abandoned.
 *
 * A body that never emits a blank line - a proxy streaming something that is
 * not SSE, or a truncated stream - would otherwise accumulate whole in memory.
 * Generous for these events: the largest of the four carries one summary, and
 * a summary is spans the model marked rather than the documents themselves.
 *
 * Counted in UTF-16 code units, which is what `length` reports - so the real
 * byte ceiling for non-ASCII content is up to twice this. At this magnitude
 * that is a naming matter rather than a sizing one.
 */
const MAX_PENDING_FRAME_CHARS = 4 * 1024 * 1024

export class ParsedFrameTooLarge extends Error {
  constructor() {
    super('The stream sent more than one event of unterminated data.')
    this.name = 'ParsedFrameTooLarge'
  }
}

export class EventStreamParser {
  private buffer = ''

  // Where the last search for a boundary got to. Without it every chunk
  // rescans the whole buffer from the start, which is quadratic in the length
  // of a frame - a boundary-free body would freeze the tab well before it
  // exhausted memory.
  private searchedTo = 0

  // Set once the buffer passes the cap. The frames this push already completed
  // are still returned - a chunk carrying a whole `result` followed by junk
  // must not lose the summary that did arrive - and the next push refuses.
  private overflowed = false

  // A trailing carriage return whose newline has not arrived yet.
  private carriageReturn = ''

  /**
   * The complete event payloads this chunk finished, in order.
   *
   * @throws ParsedFrameTooLarge when one unterminated frame grows past the cap.
   */
  push(chunk: string): string[] {
    if (this.overflowed) throw new ParsedFrameTooLarge()

    // A chunk can end mid-CRLF. Normalising it on its own would turn that one
    // line break into two, splitting a multi-line `data` field across two
    // frames and leaving both halves unparsable. The carriage return is held
    // back until the character after it is known.
    const pending = this.carriageReturn + chunk
    const endsOnReturn = pending.endsWith('\r')
    this.carriageReturn = endsOnReturn ? '\r' : ''

    // A frame boundary is a blank line however the sender ends its lines, and
    // a CRLF left alone would leave a stray return inside the JSON.
    this.buffer += (endsOnReturn ? pending.slice(0, -1) : pending).replace(
      /\r\n|\r/g,
      '\n'
    )

    const payloads: string[] = []
    // One character back, so a boundary split across two chunks is still seen.
    let boundary = this.buffer.indexOf('\n\n', Math.max(this.searchedTo - 1, 0))

    while (boundary !== -1) {
      const frame = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)

      const payload = dataOf(frame)
      if (payload !== null) payloads.push(payload)

      boundary = this.buffer.indexOf('\n\n')
    }

    this.searchedTo = this.buffer.length

    if (this.buffer.length > MAX_PENDING_FRAME_CHARS) {
      // Dropped rather than grown: whatever is arriving is not this stream.
      this.buffer = ''
      this.searchedTo = 0
      this.carriageReturn = ''
      this.overflowed = true
    }

    return payloads
  }
}

/** The `data` field of one frame, or nothing when it carries none. */
function dataOf(frame: string): string | null {
  const lines = frame
    .split('\n')
    .filter(line => line.startsWith('data:'))
    // One optional space after the colon is part of the format, not content.
    .map(line => line.slice('data:'.length).replace(/^ /, ''))

  return lines.length > 0 ? lines.join('\n') : null
}
