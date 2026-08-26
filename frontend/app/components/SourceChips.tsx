import type { SelectedDocument } from '../lib/documentSelection'
import { readableDocumentName } from '../lib/documentName'
import { Icon } from './Icon'

interface Props {
  documents: SelectedDocument[]
}

/**
 * The documents this summary was built from.
 *
 * The names come from the clinician's own selection, not from the response:
 * the analysis endpoint answers with the entities of each document in
 * submission order and never echoes a filename back.
 */
export function SourceChips({ documents }: Props) {
  if (documents.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <span className="text-[11px] font-semibold tracking-[0.09em] uppercase text-ink-muted">
        Lu dans
      </span>
      <ul className="flex flex-wrap gap-2.5">
        {documents.map(({ id, file }) => (
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
          </li>
        ))}
      </ul>
    </div>
  )
}
