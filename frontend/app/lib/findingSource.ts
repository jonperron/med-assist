import type { Finding } from '../types/extraction'
import type { SelectedDocument } from './documentSelection'
import { readableDocumentName } from './documentName'

/**
 * Name the documents a finding came from.
 *
 * `Finding.documents` holds indices into the batch the clinician submitted, in
 * that same order, so the name comes from the selection this page already
 * holds rather than from the response: the analysis path never echoes a
 * filename back, and it does not have to for this to read.
 *
 * One document is named. Several are counted, because four names on the right
 * of a row is not something a clinician reads - the count says the finding is
 * agreed on, which is the clinical fact, and the source chips above say which
 * documents were read at all.
 */
export function sourceLabel(
  finding: Finding,
  documents: SelectedDocument[]
): string | null {
  // Defensive on both ends. An index the selection cannot resolve means the
  // page state and the response disagree - a batch replaced mid-request, or a
  // response that is not ours - and an unnamed row beats a wrong name.
  const resolvable = finding.documents.filter(
    index => Number.isInteger(index) && index >= 0 && index < documents.length
  )

  if (resolvable.length === 0) return null
  if (resolvable.length === 1) {
    return readableDocumentName(documents[resolvable[0]].file.name)
  }

  return `${resolvable.length} documents`
}
