import type { AnalyzedDocument } from '../types/extraction'
import type { SelectedDocument } from './documentSelection'
import { readableDocumentName } from './documentName'

/**
 * Which submitted documents are not behind the summary.
 *
 * Since #66 a batch holding one file nothing could be read from still answers
 * 200: the document keeps its position in `AnalysisResponse.documents` with
 * `read` false, and the summary is built from the rest. That fails open - the
 * clinician learns a document was skipped only if the interface says so, and a
 * summary quietly missing a document is worse than a refusal.
 *
 * The API names the position, never the file. The name comes back from the
 * selection this page holds; a position it cannot resolve is numbered rather
 * than left out, because an unnamed gap still has to be reported.
 */
export function unreadDocuments(
  analyzed: AnalyzedDocument[],
  documents: SelectedDocument[]
): string[] {
  return analyzed.flatMap((document, index) => {
    if (document.read) return []

    const selected = documents[index]
    return [
      selected ? readableDocumentName(selected.file.name) : `Document ${index + 1}`,
    ]
  })
}

/** True when the API read this position, or said nothing about it at all. */
export function wasRead(
  analyzed: AnalyzedDocument[],
  index: number
): boolean {
  const document = analyzed[index]
  // An absent entry is not a failed one. A response carrying fewer documents
  // than were selected is not ours, and marking every unmatched chip unread
  // would report failures that did not happen.
  return document === undefined || document.read
}
