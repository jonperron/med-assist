import { describe, expect, it } from 'vitest'
import { unreadDocuments, wasRead } from '../unreadDocuments'
import type { AnalyzedDocument } from '../../types/extraction'
import type { SelectedDocument } from '../documentSelection'

function analyzed(read: boolean[]): AnalyzedDocument[] {
  return read.map(wasItRead => ({
    patient_info: [],
    anatomy: [],
    symptoms: [],
    examinations: [],
    treatments: [],
    pathologies: [],
    temporal: [],
    measurements: [],
    other: [],
    read: wasItRead,
    unreadable_reason: wasItRead ? null : ('no_text' as const),
    document_date: null,
  }))
}

function documents(names: string[]): SelectedDocument[] {
  return names.map((name, index) => ({
    id: `document-${index}`,
    file: new File(['content'], name, { type: 'application/pdf' }),
  }))
}

const SELECTED = documents(['lettre-adressage.pdf', 'scan-illisible.pdf'])

describe('unreadDocuments', () => {
  it('says nothing when every document was read', () => {
    expect(unreadDocuments(analyzed([true, true]), SELECTED)).toEqual([])
  })

  it('names the document that was skipped', () => {
    expect(unreadDocuments(analyzed([true, false]), SELECTED)).toEqual([
      'Scan illisible',
    ])
  })

  it('names every skipped document, in submission order', () => {
    expect(unreadDocuments(analyzed([false, false]), SELECTED)).toEqual([
      'Lettre adressage',
      'Scan illisible',
    ])
  })

  it('numbers a position the selection cannot resolve rather than dropping it', () => {
    expect(unreadDocuments(analyzed([true, true, false]), SELECTED)).toEqual([
      'Document 3',
    ])
  })

  it('handles a response carrying no documents at all', () => {
    expect(unreadDocuments([], SELECTED)).toEqual([])
  })
})

describe('wasRead', () => {
  it('reports what the API said about the position', () => {
    expect(wasRead(analyzed([true, false]), 0)).toBe(true)
    expect(wasRead(analyzed([true, false]), 1)).toBe(false)
  })

  it('treats a position the response says nothing about as read', () => {
    // A short response is not ours. Marking every unmatched chip unread would
    // report failures that did not happen.
    expect(wasRead(analyzed([true]), 3)).toBe(true)
    expect(wasRead([], 0)).toBe(true)
  })
})
