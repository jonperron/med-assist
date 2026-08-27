import { describe, expect, it } from 'vitest'
import { documentFinished, startReading } from '../readingState'

describe('startReading', () => {
  it('puts the first document in flight and leaves the rest waiting', () => {
    expect(startReading(3)).toEqual({
      states: ['reading', 'pending', 'pending'],
      finished: 0,
    })
  })

  it('handles a batch of nothing', () => {
    expect(startReading(0)).toEqual({ states: [], finished: 0 })
  })
})

describe('documentFinished', () => {
  it('ticks the reported document and starts the next one', () => {
    const state = documentFinished(startReading(3), 0, true)

    expect(state.states).toEqual(['read', 'reading', 'pending'])
    expect(state.finished).toBe(1)
  })

  it('marks a document the batch could not read', () => {
    const state = documentFinished(startReading(2), 0, false)

    expect(state.states).toEqual(['unread', 'reading'])
    expect(state.finished).toBe(1)
  })

  it('counts a whole batch through to the end', () => {
    let state = startReading(2)
    state = documentFinished(state, 0, true)
    state = documentFinished(state, 1, true)

    expect(state.states).toEqual(['read', 'read'])
    expect(state.finished).toBe(2)
  })

  it('ignores an index the batch does not have', () => {
    const start = startReading(2)
    expect(documentFinished(start, 5, true)).toBe(start)
    expect(documentFinished(start, -1, true)).toBe(start)
    expect(documentFinished(start, 1.5, true)).toBe(start)
  })

  it('cannot push the counter past the batch when an event repeats', () => {
    let state = startReading(2)
    state = documentFinished(state, 0, true)
    state = documentFinished(state, 0, true)

    expect(state.finished).toBe(1)
    expect(state.states).toEqual(['read', 'reading'])
  })

  it('does not put a finished document back in flight', () => {
    let state = startReading(3)
    state = documentFinished(state, 1, true)
    state = documentFinished(state, 0, true)

    expect(state.states).toEqual(['read', 'read', 'reading'])
    expect(state.finished).toBe(2)
  })
})
