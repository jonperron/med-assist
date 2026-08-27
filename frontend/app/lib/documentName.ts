/**
 * Turn a filename into something that reads as a document in a summary.
 *
 * The clinician chose these files, so the name is the only handle they have on
 * which document a source chip refers to. It is shown, never sent anywhere and
 * never stored: it stays in page state for the life of the summary.
 *
 * A filename is untrusted text like any other, so it goes through the same
 * stripping as everything else on screen - a name that displays as something
 * other than what it is would mean a source chip naming a document that was
 * not the one read.
 */
import { stripInvisible } from './safeText'

// Long enough for any real document name, short enough that one cannot push
// the rest of a row off screen.
const MAX_DISPLAY_LENGTH = 120

/** Make a filename safe to display, without changing how it reads. */
export function displayFilename(filename: string): string {
  const cleaned = stripInvisible(filename)
  if (cleaned.length <= MAX_DISPLAY_LENGTH) return cleaned

  return cleaned.slice(0, MAX_DISPLAY_LENGTH - 1) + '…'
}

/** Drop the extension and read the name as words, for a source chip. */
export function readableDocumentName(filename: string): string {
  const safe = displayFilename(filename)
  const withoutExtension = safe.replace(/\.[^./\\]+$/, '')
  const spaced = withoutExtension.replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim()

  // A name that was nothing but an extension, or nothing but separators, has
  // no readable form. Falling back to the filename beats an empty chip.
  if (!spaced) return safe

  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
