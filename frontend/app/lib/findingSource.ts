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
 * That is about the response only. The request still carries every filename to
 * the API host, in the multipart part headers - which is the boundary
 * `NEXT_PUBLIC_API_URL` defines, and is why it has to point at a host the
 * documents are allowed to reach.
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
  // Defensive on both ends. A finding carrying no indices at all is the
  // pre-#66 shape, or a body that is not ours; calling `.filter` on it would
  // throw inside a client component, and a blank page is worse than an
  // unlabelled row. An index the selection cannot resolve means page state and
  // the response disagree, and an unnamed row beats a wrong name.
  if (!Array.isArray(finding?.documents)) return null

  const resolvable = finding.documents.filter(
    index => Number.isInteger(index) && index >= 0 && index < documents.length
  )

  if (resolvable.length === 0) return null
  if (resolvable.length === 1) {
    return readableDocumentName(documents[resolvable[0]].file.name)
  }

  return `${resolvable.length} documents`
}
