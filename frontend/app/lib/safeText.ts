/**
 * Make a string from outside this app safe to display.
 *
 * Everything on the summary screen is untrusted text whoever wrote it:
 * AGENTS.md section 9 says so of uploaded content, and a finding is a span
 * lifted straight out of a document. Invisible formatting characters let such
 * a string display in an order or a shape the document does not say - on the
 * one screen a clinician is told to trust, and one they may print into a
 * patient file.
 *
 * This changes how a string displays, never what it says. It is applied at the
 * render boundary rather than on the way in, so nothing downstream has to
 * remember to do it.
 */

// Format characters and controls carry the bidirectional overrides. The line
// and paragraph separators are here because a browser renders them as a line
// break inside a text node, which would let one finding split across two rows.
const INVISIBLE = /[\p{Cf}\p{Cc}\p{Zl}\p{Zp}]/gu

// Runs of exotic spaces collapse to one: they are legitimate in some scripts
// but a long run is a way to push the rest of a row out of sight.
const SPACES = /\p{Zs}+/gu

export function stripInvisible(value: string): string {
  return value.replace(INVISIBLE, '').replace(SPACES, ' ').trim()
}

/**
 * The same, for a value that is only claimed to be a string.
 *
 * Response fields reach the render boundary having been shape-checked at the
 * level above, not at every leaf. A number or an object here is a body that is
 * not ours, and an empty cell beats React refusing to render the page.
 */
export function safeText(value: unknown): string {
  return typeof value === 'string' ? stripInvisible(value) : ''
}
