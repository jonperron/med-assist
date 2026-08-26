import { describe, expect, it } from 'vitest'
import { describeRejection, isAccepted, MAX_FILES } from '../documentSelection'

function file(name: string, type: string): File {
  return new File(['content'], name, { type })
}

const PDF = file('lettre.pdf', 'application/pdf')
const TEXT = file('note.txt', 'text/plain')

describe('isAccepted', () => {
  it('accepts the three supported formats', () => {
    expect(isAccepted(PDF)).toBe(true)
    expect(isAccepted(TEXT)).toBe(true)
    expect(
      isAccepted(
        file(
          'suivi.docx',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
      )
    ).toBe(true)
  })

  it('refuses a supported extension carrying another type', () => {
    expect(isAccepted(file('lettre.pdf', 'image/png'))).toBe(false)
  })

  it('refuses a supported type under another extension', () => {
    expect(isAccepted(file('lettre.exe', 'application/pdf'))).toBe(false)
  })
})

describe('describeRejection', () => {
  it('accepts a valid selection', () => {
    expect(describeRejection([PDF, TEXT], 0)).toBeNull()
  })

  it('refuses the whole selection when one document is unsupported', () => {
    const rejection = describeRejection([PDF, file('scan.png', 'image/png')], 0)
    expect(rejection).toMatch(/PDF, DOCX ou TXT/)
  })

  it('counts what is already selected against the cap', () => {
    expect(describeRejection([PDF], MAX_FILES - 1)).toBeNull()
    expect(describeRejection([PDF], MAX_FILES)).toMatch(String(MAX_FILES))
  })
})
