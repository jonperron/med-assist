import type { SelectedDocument } from '../lib/documentSelection'
import { displayFilename } from '../lib/documentName'
import type { DocumentReadState } from '../lib/readingState'
import { Icon } from './Icon'

interface Props {
  documents: SelectedDocument[]
  /** One state per document, in submission order. */
  states: DocumentReadState[]
  /** How many documents have been reported on so far. */
  finished: number
}

function readingLabel(count: number): string {
  return count === 1 ? 'Lecture du document' : `Lecture de ${count} documents`
}

const MARKS = {
  pending: { name: 'document', className: 'text-source', spin: false },
  reading: { name: 'spinner', className: 'text-accent', spin: true },
  read: { name: 'check', className: 'text-accent', spin: false },
  unread: { name: 'warning', className: 'text-caution', spin: false },
} as const

/**
 * How far the analysis has got.
 *
 * `POST /api/analyze/stream` reports each document as it is read, so this is a
 * real count rather than a sweep: the bar fills, the counter says how many of
 * how many, and each row carries a tick, a spinner or a caution mark. A
 * clinician can tell a slow batch from a stalled one, which one spinner over
 * the lot cannot say.
 *
 * The events carry a position and a boolean. The names are the ones already on
 * screen from the selection - nothing about a document comes back to be shown
 * here.
 */
export function ReadingProgress({ documents, states, finished }: Props) {
  const total = documents.length
  const share = total === 0 ? 0 : Math.min(finished / total, 1)

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col gap-3.5 rounded-[10px] border border-rule bg-surface px-7 py-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className="font-serif text-[22px] text-ink">{readingLabel(total)}</span>
        <span className="text-[13.5px] text-ink-muted">
          {finished} sur {total}
        </span>
      </div>

      <span className="block h-1.5 w-full overflow-hidden rounded-[3px] bg-rule-soft">
        <span
          className="block h-1.5 rounded-[3px] bg-accent transition-[width] duration-300"
          style={{ width: `${Math.round(share * 100)}%` }}
        />
      </span>

      <ul>
        {documents.map(({ id, file }, index) => {
          const mark = MARKS[states[index] ?? 'pending']
          return (
            <li
              key={id}
              className="flex items-center gap-3 border-t border-rule-soft py-2.5"
            >
              <Icon
                name={mark.name}
                size={17}
                strokeWidth={1.8}
                className={`shrink-0 ${mark.className} ${mark.spin ? 'animate-spin' : ''}`}
              />
              <span
                className={`grow text-[14.5px] break-all ${
                  states[index] === 'pending' ? 'text-ink-muted' : 'text-ink'
                }`}
              >
                {displayFilename(file.name)}
              </span>
              {states[index] === 'unread' && (
                <span className="shrink-0 text-[12.5px] text-caution-ink">non lu</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
