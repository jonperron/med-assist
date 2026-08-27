import { Icon } from './Icon'

interface Props {
  /** The documents the batch could not read, in submission order. */
  names: string[]
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
export function UnreadNotice({ names }: Props) {
  if (names.length === 0) return null

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
          {names.join(', ')} — le résumé ci-dessous ne les contient pas. Vérifiez
          qu&apos;il s&apos;agit bien d&apos;un PDF, d&apos;un DOCX ou d&apos;un TXT
          contenant du texte, et non d&apos;une image scannée.
        </span>
      </div>
    </div>
  )
}
