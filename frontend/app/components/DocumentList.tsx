'use client'

import type { SelectedDocument } from '../lib/documentSelection'
import { Icon } from './Icon'

interface Props {
  documents: SelectedDocument[]
  onRemove: (id: string) => void
  onRemoveAll: () => void
}

function readyLabel(count: number): string {
  return count === 1 ? '1 document prêt' : `${count} documents prêts`
}

export function DocumentList({ documents, onRemove, onRemoveAll }: Props) {
  if (documents.length === 0) return null

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-baseline justify-between border-b border-edge pb-2.5">
        <span className="text-[11px] font-semibold tracking-[0.09em] uppercase text-ink-muted">
          {readyLabel(documents.length)}
        </span>
        <button
          type="button"
          onClick={onRemoveAll}
          className="cursor-pointer text-[13px] font-semibold text-accent hover:text-accent-strong hover:underline"
        >
          Tout retirer
        </button>
      </div>

      <ul>
        {documents.map(({ id, file }) => (
          <li
            key={id}
            className="flex items-center gap-3.5 border-b border-rule-soft py-3.5"
          >
            <Icon
              name="document"
              size={18}
              strokeWidth={1.5}
              className="shrink-0 text-ink-muted"
            />
            <span className="grow text-[15px] break-all text-ink">{file.name}</span>
            <button
              type="button"
              onClick={() => onRemove(id)}
              aria-label={`Retirer ${file.name}`}
              className="flex size-11 shrink-0 cursor-pointer items-center justify-center text-source hover:text-ink"
            >
              <Icon name="close" size={16} strokeWidth={1.8} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
