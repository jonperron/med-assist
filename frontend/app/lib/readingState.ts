/**
 * What the interface knows about each document while the batch is being read.
 *
 * `POST /api/analyze/stream` reports documents in submission order, one event
 * each. Everything before the reported position is finished, the position
 * after it is the one in flight, and the rest are waiting.
 */

export type DocumentReadState = 'pending' | 'reading' | 'read' | 'unread'

export interface ReadingState {
  states: DocumentReadState[]
  /** How many documents have been reported on. The counter's numerator. */
  finished: number
}

/** Nothing read yet: the first document is in flight, the rest are waiting. */
export function startReading(total: number): ReadingState {
  return {
    states: Array.from({ length: total }, (_, index) =>
      index === 0 ? 'reading' : 'pending'
    ),
    finished: 0,
  }
}

/**
 * Fold one `document` event in.
 *
 * The index comes off the wire, so it is bounds-checked: an event for a
 * position this batch does not have would otherwise grow the list and put a
 * row on screen with no document behind it.
 *
 * `finished` counts the positions actually reported rather than the highest
 * index seen, so a repeated event cannot push the bar past full.
 */
export function documentFinished(
  current: ReadingState,
  index: number,
  read: boolean
): ReadingState {
  if (!Number.isInteger(index) || index < 0 || index >= current.states.length) {
    return current
  }

  const states = current.states.map((state, position) => {
    if (position === index) return read ? 'read' : 'unread'
    // The next one is in flight; documents are read in submission order.
    if (position === index + 1 && state === 'pending') return 'reading'
    return state
  })

  return {
    states,
    finished: states.filter(state => state === 'read' || state === 'unread').length,
  }
}
