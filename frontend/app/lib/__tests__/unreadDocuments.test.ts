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

  it('names the document that was skipped, with the reason the API gave', () => {
    expect(unreadDocuments(analyzed([true, false]), SELECTED)).toEqual([
      { name: 'Scan illisible', reason: 'no_text' },
    ])
  })

  it('names every skipped document, in submission order', () => {
    expect(unreadDocuments(analyzed([false, false]), SELECTED)).toEqual([
      { name: 'Lettre adressage', reason: 'no_text' },
      { name: 'Scan illisible', reason: 'no_text' },
    ])
  })

  it('numbers a position the selection cannot resolve rather than dropping it', () => {
    expect(unreadDocuments(analyzed([true, true, false]), SELECTED)).toEqual([
      { name: 'Document 3', reason: 'no_text' },
    ])
  })

  it('drops a reason this build has never heard of rather than passing it on', () => {
    // `UnreadableReason` is documented as a set that will grow, and the notice
    // gives advice specific to the one member this build knows.
    const grown = analyzed([false])
    const withNewReason = [
      { ...grown[0], unreadable_reason: 'encrypted' as unknown as 'no_text' },
    ]

    expect(unreadDocuments(withNewReason, SELECTED)).toEqual([
      { name: 'Lettre adressage', reason: null },
    ])
  })

  it('reports nothing rather than throwing when documents is not a list', () => {
    expect(
      unreadDocuments(null as unknown as ReturnType<typeof analyzed>, SELECTED)
    ).toEqual([])
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
