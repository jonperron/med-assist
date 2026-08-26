import type { SummarySection } from '../types/extraction'

/**
 * The order the summary is read in, and the one section that is not a card.
 *
 * The backend returns its sections in its own reading order; this is the
 * layout's order, which pairs the two long sections down one column and the
 * two short ones down the other.
 */
const CARD_ORDER: readonly string[] = [
  'pathologies',
  'treatments',
  'symptoms',
  'examinations',
]

/**
 * Anatomy is a list of sites. On its own it says nothing clinical, but beside
 * the symptoms it came from it does, so it becomes a quiet line under them
 * rather than a card of its own.
 */
const SITES_KEY = 'anatomy'

const SITES_HOST_KEY = 'symptoms'

export interface SummaryLayout {
  cards: SummarySection[]
  /** Rendered under the symptoms card, or as its own card when there is none. */
  sites: SummarySection | null
}

export function layoutSummary(sections: SummarySection[]): SummaryLayout {
  const sites = sections.find(section => section.key === SITES_KEY) ?? null
  const hasHost = sections.some(section => section.key === SITES_HOST_KEY)

  // Anything the backend adds that this layout has not heard of is appended in
  // the order it arrived. Dropping it would silently lose clinical content.
  const remaining = sections.filter(
    section => section.key !== SITES_KEY || !hasHost
  )

  const cards = [...remaining].sort((left, right) => {
    const leftRank = CARD_ORDER.indexOf(left.key)
    const rightRank = CARD_ORDER.indexOf(right.key)
    if (leftRank === rightRank) return 0
    if (leftRank === -1) return 1
    if (rightRank === -1) return -1
    return leftRank - rightRank
  })

  return { cards, sites: hasHost ? sites : null }
}

export { SITES_HOST_KEY }
