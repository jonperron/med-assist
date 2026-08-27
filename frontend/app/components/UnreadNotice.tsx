import type { UnreadDocument } from '../lib/unreadDocuments'
import { Icon } from './Icon'

interface Props {
  /** The documents the batch could not read, in submission order. */
  documents: UnreadDocument[]
}

function headline(count: number): string {
  return count === 1
    ? "Un document n'a pas pu être lu"
    : `${count} documents n'ont pas pu être lus`
}

/**
 * What the summary below is missing.
 *
 * A batch holding an unreadable document is answered rather than refused, so
 * the summary that follows is built from fewer documents than were submitted.
 * That has to be said: a summary quietly missing a document reads as complete,
 * and a clinician acting on it would be acting on less than they think.
 *
 * Kept in the printed copy on purpose - on a page going into a patient file,
 * what was left out matters as much as what was read.
 */
export function UnreadNotice({ documents }: Props) {
  if (documents.length === 0) return null

  const names = documents.map(document => document.name)
  // The remedy is specific to `no_text`, which is the only reason the API can
  // send today. A reason this build does not know gets the neutral wording
  // rather than advice that may not apply to it.
  const allNoText = documents.every(document => document.reason === 'no_text')

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-caution-edge bg-caution-tint px-[18px] py-4"
    >
      <Icon
        name="warning"
        size={18}
        strokeWidth={1.7}
        className="mt-px shrink-0 text-caution"
      />
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold text-caution-ink">
          {headline(names.length)}
        </span>
        <span className="text-[13.5px] leading-[1.55] text-pretty text-caution-ink">
          {names.join(', ')} — le résumé ci-dessous ne les contient pas.
          {allNoText
            ? " Vérifiez qu'il s'agit bien d'un PDF, d'un DOCX ou d'un TXT contenant du texte, et non d'une image scannée."
            : ' Relisez-les directement.'}
        </span>
      </div>
    </div>
  )
}
