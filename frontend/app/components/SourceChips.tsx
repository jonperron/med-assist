import type { AnalyzedDocument } from '../types/extraction'
import type { SelectedDocument } from '../lib/documentSelection'
import { formatDocumentDate } from '../lib/documentDate'
import { readableDocumentName } from '../lib/documentName'
import { Icon } from './Icon'

interface Props {
  documents: SelectedDocument[]
  /** The same documents as the API reported them, in submission order. */
  analyzed: AnalyzedDocument[]
}

/** Names the list as well as heading it, so the chips are addressable. */
const SOURCES_LABEL = 'Lu dans'

/**
 * The documents this summary was built from.
 *
 * The names come from the clinician's own selection, not from the response:
 * the analysis endpoint answers with the entities of each document in
 * submission order and never echoes a filename back. The dates do come from
 * the response - `AnalyzedDocument.document_date` is the date the document
 * carries in its own head, which is what places it on a timeline, and is not
 * something the browser can read off a file.
 *
 * A document with no date is left undated rather than guessed at. Null is the
 * common answer there and is not a fault.
 */
export function SourceChips({ documents, analyzed }: Props) {
  if (documents.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <span className="text-[11px] font-semibold tracking-[0.09em] uppercase text-ink-muted">
        {SOURCES_LABEL}
      </span>
      <ul aria-label={SOURCES_LABEL} className="flex flex-wrap gap-2.5">
        {documents.map(({ id, file }, index) => {
          const date = formatDocumentDate(analyzed[index]?.document_date)
          return (
            <li
              key={id}
              className="flex items-center gap-2.5 rounded-lg border border-rule bg-surface px-3.5 py-2.5"
            >
              <Icon
                name="document"
                size={15}
                strokeWidth={1.5}
                className="shrink-0 text-source"
              />
              <span className="text-[13.5px] font-semibold text-ink">
                {readableDocumentName(file.name)}
              </span>
              {date && (
                <span className="text-[12.5px] text-ink-muted">{date}</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
