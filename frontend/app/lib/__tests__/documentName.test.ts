import { describe, expect, it } from 'vitest'
import { readableDocumentName } from '../documentName'

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
