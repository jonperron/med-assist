import { describe, expect, it } from 'vitest'
import { safeText, stripInvisible } from '../safeText'

// Written as escapes on purpose: these characters are invisible in a diff, and
// a test asserting they are stripped must not itself hide them from a reviewer.
const RIGHT_TO_LEFT_OVERRIDE = '\u202E'
const ZERO_WIDTH_SPACE = '\u200B'
const LINE_SEPARATOR = '\u2028'
const PARAGRAPH_SEPARATOR = '\u2029'
const BELL_CONTROL = '\u0007'
const IDEOGRAPHIC_SPACE = '\u3000'

describe('stripInvisible', () => {
  it('leaves ordinary clinical text alone', () => {
    expect(stripInvisible('Troponine I 1,10 ng/mL')).toBe('Troponine I 1,10 ng/mL')
  })

  it('drops a bidirectional override', () => {
    // It would display the span in an order the document does not say.
    expect(stripInvisible(`cirrhose${RIGHT_TO_LEFT_OVERRIDE}decompensee`)).toBe(
      'cirrhosedecompensee'
    )
  })

  it('drops a zero-width character', () => {
    expect(stripInvisible(`fie${ZERO_WIDTH_SPACE}vre`)).toBe('fievre')
  })

  it('drops a line separator that would split one finding across two rows', () => {
    expect(stripInvisible(`ictere${LINE_SEPARATOR}conjonctival`)).toBe(
      'ictereconjonctival'
    )
  })

  it('drops a paragraph separator and a control character', () => {
    expect(stripInvisible(`a${PARAGRAPH_SEPARATOR}b${BELL_CONTROL}c`)).toBe('abc')
  })

  it('collapses a run of exotic spaces that would push a row out of sight', () => {
    expect(stripInvisible(`foie${IDEOGRAPHIC_SPACE.repeat(40)}veine porte`)).toBe(
      'foie veine porte'
    )
  })

  it('trims without changing what the text says', () => {
    expect(stripInvisible('  cirrhose  ')).toBe('cirrhose')
  })

  it('handles a string made only of invisible characters', () => {
    expect(stripInvisible(`${RIGHT_TO_LEFT_OVERRIDE}${ZERO_WIDTH_SPACE}`)).toBe('')
  })
})

describe('safeText', () => {
  it('strips a string the same way', () => {
    expect(safeText(`cirrhose${RIGHT_TO_LEFT_OVERRIDE}`)).toBe('cirrhose')
  })

  it('renders nothing for a value that is not a string', () => {
    // A body that is not ours must not take the page down.
    expect(safeText(null)).toBe('')
    expect(safeText(undefined)).toBe('')
    expect(safeText(42)).toBe('')
    expect(safeText({ text: 'cirrhose' })).toBe('')
  })
})
