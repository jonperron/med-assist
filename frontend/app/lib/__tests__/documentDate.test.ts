import { describe, expect, it } from 'vitest'
import { formatDateRange, formatDocumentDate } from '../documentDate'

describe('formatDocumentDate', () => {
  it('reads a calendar date the way a clinician does', () => {
    expect(formatDocumentDate('2025-03-04')).toBe('4 mars 2025')
  })

  it('does not shift the day into the browser timezone', () => {
    // Parsed as local time, a date-only string lands on the previous day west
    // of UTC. A document on the wrong day of a timeline is the failure the
    // backend's own date rules exist to avoid.
    expect(formatDocumentDate('2025-01-01')).toBe('1 janvier 2025')
    expect(formatDocumentDate('2025-12-31')).toBe('31 décembre 2025')
  })

  it('has nothing to say about a document that carries no date', () => {
    expect(formatDocumentDate(null)).toBeNull()
    expect(formatDocumentDate(undefined)).toBeNull()
    expect(formatDocumentDate('')).toBeNull()
  })

  it('refuses anything that is not a calendar date', () => {
    expect(formatDocumentDate('2025-03')).toBeNull()
    expect(formatDocumentDate('04/03/2025')).toBeNull()
    expect(formatDocumentDate('2025-03-04T10:00:00Z')).toBeNull()
  })

  it('refuses a date that does not exist', () => {
    expect(formatDocumentDate('2025-02-31')).toBeNull()
    expect(formatDocumentDate('2025-13-01')).toBeNull()
  })
})

describe('formatDateRange', () => {
  it('says the span the batch covers', () => {
    expect(formatDateRange({ start: '2025-03-04', end: '2025-04-02' })).toBe(
      'du 4 mars au 2 avril 2025'
    )
  })

  it('keeps both years when the batch crosses one', () => {
    expect(formatDateRange({ start: '2024-11-20', end: '2025-01-08' })).toBe(
      'du 20 novembre 2024 au 8 janvier 2025'
    )
  })

  it('says a single date rather than a range of one day', () => {
    expect(formatDateRange({ start: '2025-03-04', end: '2025-03-04' })).toBe(
      '4 mars 2025'
    )
  })

  it('has nothing to say when nothing in the batch could be dated', () => {
    expect(formatDateRange(null)).toBeNull()
    expect(formatDateRange(undefined)).toBeNull()
  })

  it('says nothing rather than a line that reads backwards', () => {
    expect(formatDateRange({ start: '2025-04-02', end: '2025-03-04' })).toBeNull()
  })

  it('says nothing when either end is not a calendar date', () => {
    expect(formatDateRange({ start: 'hier', end: '2025-03-04' })).toBeNull()
    expect(formatDateRange({ start: '2025-03-04', end: '' })).toBeNull()
  })
})
