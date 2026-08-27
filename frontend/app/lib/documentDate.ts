import type { DateRange } from '../types/extraction'

/**
 * Read the dates the API supplies, and say them the way a clinician reads them.
 *
 * `AnalyzedDocument.document_date` and `ClinicalSummary.date_range` are plain
 * calendar dates - `YYYY-MM-DD`, no time and no zone. They are formatted in
 * UTC rather than the browser's zone: parsing a date-only string as local time
 * moves it a day either side of midnight, and a document on the wrong day of a
 * timeline is exactly the failure the backend's own rules refuse to risk.
 *
 * Null is the common answer and is not an error. Nothing here invents a date
 * for a document that carries none.
 */

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

const FULL = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})

const DAY_AND_MONTH = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'long',
  timeZone: 'UTC',
})

/** Parse a calendar date, or nothing when it is not one. */
function parseCalendarDate(value: string | null | undefined): Date | null {
  if (!value) return null

  const parts = ISO_DATE.exec(value)
  if (!parts) return null

  const [, year, month, day] = parts
  const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)))

  // `Date.UTC` rolls 2025-02-31 forward into March rather than refusing it.
  // Reading the components back is what catches that.
  if (
    parsed.getUTCFullYear() !== Number(year) ||
    parsed.getUTCMonth() !== Number(month) - 1 ||
    parsed.getUTCDate() !== Number(day)
  ) {
    return null
  }

  return parsed
}

/** One document's own date, or nothing when it carries none. */
export function formatDocumentDate(value: string | null | undefined): string | null {
  const parsed = parseCalendarDate(value)
  return parsed ? FULL.format(parsed) : null
}

/**
 * The span a batch covers, as one line under the summary title.
 *
 * A range whose ends fall in the same year drops the first year, so the line
 * reads "du 4 mars au 2 avril 2025" rather than repeating it. Both ends on the
 * same day is not a range at all and is said as a single date.
 */
export function formatDateRange(range: DateRange | null | undefined): string | null {
  if (!range) return null

  const start = parseCalendarDate(range.start)
  const end = parseCalendarDate(range.end)
  if (!start || !end) return null

  // The backend orders the range, so this only fires on a response that is not
  // ours. Saying nothing beats a line that reads backwards.
  if (start.getTime() > end.getTime()) return null

  if (start.getTime() === end.getTime()) return FULL.format(start)

  const sameYear = start.getUTCFullYear() === end.getUTCFullYear()
  const from = sameYear ? DAY_AND_MONTH.format(start) : FULL.format(start)

  return `du ${from} au ${FULL.format(end)}`
}
