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
export class EventStreamParser {
  private buffer = ''

  /** The complete event payloads this chunk finished, in order. */
  push(chunk: string): string[] {
    // Normalised first: a frame boundary is a blank line however the sender
    // ends its lines, and CRLF would otherwise leave a stray return inside
    // the JSON.
    this.buffer += chunk.replace(/\r\n|\r/g, '\n')

    const payloads: string[] = []
    let boundary = this.buffer.indexOf('\n\n')

    while (boundary !== -1) {
      const frame = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)

      const payload = dataOf(frame)
      if (payload !== null) payloads.push(payload)

      boundary = this.buffer.indexOf('\n\n')
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
