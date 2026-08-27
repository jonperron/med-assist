import { describe, expect, it } from 'vitest'
import {
  describeRejection,
  isAccepted,
  MAX_FILE_SIZE_BYTES,
  MAX_FILES,
} from '../documentSelection'

function file(name: string, type: string, size = 10): File {
  const made = new File(['content'], name, { type })
  Object.defineProperty(made, 'size', { value: size })
  return made
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

describe('describeRejection size and type wording', () => {
  it('refuses a document past the per-file ceiling', () => {
    const heavy = file('gros.pdf', 'application/pdf', MAX_FILE_SIZE_BYTES + 1)
    expect(describeRejection([heavy], 0)).toMatch(/volumineux/)
  })

  it('accepts a document exactly at the ceiling', () => {
    const exact = file('juste.pdf', 'application/pdf', MAX_FILE_SIZE_BYTES)
    expect(describeRejection([exact], 0)).toBeNull()
  })

  it('does not tell a clinician the format is wrong when only the type is unknown', () => {
    const docx = file('suivi.docx', 'application/octet-stream')
    const rejection = describeRejection([docx], 0)

    expect(rejection).toMatch(/navigateur/)
    expect(rejection).not.toMatch(/invalide/)
  })

  it('still refuses a genuinely unsupported format plainly', () => {
    expect(describeRejection([file('scan.png', 'image/png')], 0)).toMatch(/invalide/)
  })
})
