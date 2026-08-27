import { describe, expect, it } from 'vitest'
import { sourceLabel } from '../findingSource'
import type { SelectedDocument } from '../documentSelection'

function documents(names: string[]): SelectedDocument[] {
  return names.map((name, index) => ({
    id: `document-${index}`,
    file: new File(['content'], name, { type: 'application/pdf' }),
  }))
}

const SELECTED = documents([
  'lettre-adressage.pdf',
  'compte-rendu-ecg.pdf',
  'biologie.pdf',
])

describe('sourceLabel', () => {
  it('names the document when a finding came from exactly one', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [1] }, SELECTED)).toBe(
      'Compte rendu ecg'
    )
  })

  it('counts the documents when several agree', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [0, 2] }, SELECTED)).toBe(
      '2 documents'
    )
  })

  it('has nothing to say when the finding names no document', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [] }, SELECTED)).toBeNull()
  })

  it('drops an index the selection cannot resolve', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [0, 9] }, SELECTED)).toBe(
      'Lettre adressage'
    )
  })

  it('returns nothing rather than a wrong name when no index resolves', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [9] }, SELECTED)).toBeNull()
  })

  it('refuses a negative or fractional index', () => {
    expect(sourceLabel({ text: 'cirrhose', documents: [-1, 1.5] }, SELECTED)).toBeNull()
  })

  it('returns nothing rather than throwing on a finding from before #66', () => {
    // `findings` used to be `string[]`. Calling `.filter` on a missing field
    // would throw inside a client component and take the page down.
    const old = { text: 'cirrhose' } as unknown as Parameters<typeof sourceLabel>[0]
    expect(sourceLabel(old, SELECTED)).toBeNull()
  })

  it('returns nothing when documents is not a list', () => {
    const wrong = { text: 'cirrhose', documents: 3 } as unknown as Parameters<
      typeof sourceLabel
    >[0]
    expect(sourceLabel(wrong, SELECTED)).toBeNull()
  })

  it('strips invisible characters out of the document it names', () => {
    const selected = documents(['lettre‮-adressage.pdf'])
    expect(sourceLabel({ text: 'cirrhose', documents: [0] }, selected)).toBe(
      'Lettre adressage'
    )
  })
})
