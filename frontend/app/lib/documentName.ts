/**
 * Turn a filename into something that reads as a document in a summary.
 *
 * The clinician chose these files, so the name is the only handle they have on
 * which document a source chip refers to. It is shown, never sent anywhere and
 * never stored: it stays in page state for the life of the summary.
 */
export function readableDocumentName(filename: string): string {
  const withoutExtension = filename.replace(/\.[^./\\]+$/, '')
  const spaced = withoutExtension.replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim()

  // A name that was nothing but an extension, or nothing but separators, has
  // no readable form. Falling back to the raw filename beats an empty chip.
  if (!spaced) return filename

  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
