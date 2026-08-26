import { describe, expect, it } from 'vitest'
import { displayFilename, readableDocumentName } from '../documentName'

describe('readableDocumentName', () => {
  it('drops the extension and reads the name as words', () => {
    expect(readableDocumentName('lettre-adressage.pdf')).toBe('Lettre adressage')
    expect(readableDocumentName('compte_rendu_ecg.docx')).toBe('Compte rendu ecg')
  })

  it('drops only the last extension', () => {
    expect(readableDocumentName('scan.v2.pdf')).toBe('Scan.v2')
  })

  it('collapses runs of separators', () => {
    expect(readableDocumentName('sortie--hospitalisation__mars.txt')).toBe(
      'Sortie hospitalisation mars'
    )
  })

  it('falls back to the filename when nothing readable is left', () => {
    expect(readableDocumentName('.txt')).toBe('.txt')
    expect(readableDocumentName('---.pdf')).toBe('---.pdf')
  })

  it('leaves a name that is already readable alone', () => {
    expect(readableDocumentName('Compte rendu.pdf')).toBe('Compte rendu')
  })
})

describe('displayFilename', () => {
  it('leaves an ordinary name alone', () => {
    expect(displayFilename('lettre-adressage.pdf')).toBe('lettre-adressage.pdf')
  })

  it('strips bidirectional overrides that disguise what a file is', () => {
    expect(displayFilename('lettre\u202Efdp.pdf')).toBe('lettrefdp.pdf')
  })

  it('strips zero-width and control characters', () => {
    expect(displayFilename('note\u200B\u0007.txt')).toBe('note.txt')
  })

  it('clamps a name too long to sit in a row', () => {
    const long = 'a'.repeat(400) + '.pdf'
    const shown = displayFilename(long)
    expect(shown.length).toBeLessThanOrEqual(120)
    expect(shown.endsWith('\u2026')).toBe(true)
  })
})

describe('readableDocumentName sanitising', () => {
  it('strips invisible characters before reading the name', () => {
    expect(readableDocumentName('compte\u202E-rendu.pdf')).toBe('Compte rendu')
  })
})
