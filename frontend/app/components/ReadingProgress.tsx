import type { SelectedDocument } from '../lib/documentSelection'
import { Icon } from './Icon'

interface Props {
  documents: SelectedDocument[]
}

function readingLabel(count: number): string {
  return count === 1 ? 'Lecture du document' : `Lecture de ${count} documents`
}

/**
 * What the interface can honestly say while the analysis runs.
 *
 * The documents are summarised by a single request that answers once, so there
 * is no per-document progress to show and no count of documents finished. The
 * bar sweeps rather than fills, and every document is marked pending until the
 * whole summary arrives.
 */
export function ReadingProgress({ documents }: Props) {
  return (
    <div
      role="status"
      className="flex flex-col gap-3.5 rounded-[10px] border border-rule bg-surface px-7 py-6"
    >
      <span className="font-serif text-[22px] text-ink">
        {readingLabel(documents.length)}
      </span>

      <span className="block h-1.5 w-full overflow-hidden rounded-[3px] bg-rule-soft">
        <span className="reading-sweep block h-1.5 w-1/3 rounded-[3px] bg-accent" />
      </span>

      <ul>
        {documents.map(({ id, file }) => (
          <li key={id} className="flex items-center gap-3 border-t border-rule-soft py-2.5">
            <Icon
              name="spinner"
              size={17}
              strokeWidth={1.8}
              className="animate-spin shrink-0 text-accent"
            />
            <span className="grow text-[14.5px] break-all text-ink">{file.name}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
