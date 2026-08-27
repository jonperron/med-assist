import { describe, expect, it } from 'vitest'
import { layoutSummary } from '../summaryLayout'
import type { SummarySection } from '../../types/extraction'

function section(key: string, heading = key): SummarySection {
  return {
    key,
    heading,
    sentence: `${heading}.`,
    findings: [{ text: heading, documents: [0] }],
  }
}

function keysOf(sections: SummarySection[]): string[] {
  return sections.map(entry => entry.key)
}

describe('layoutSummary', () => {
  it('lays the four clinical sections out in reading order', () => {
    const { cards } = layoutSummary([
      section('examinations'),
      section('symptoms'),
      section('treatments'),
      section('pathologies'),
    ])

    expect(keysOf(cards)).toEqual([
      'pathologies',
      'treatments',
      'symptoms',
      'examinations',
    ])
  })

  it('folds anatomy under the symptoms rather than giving it a card', () => {
    const { cards, sites } = layoutSummary([section('symptoms'), section('anatomy')])

    expect(keysOf(cards)).toEqual(['symptoms'])
    expect(sites?.key).toBe('anatomy')
  })

  it('keeps anatomy as a card when there are no symptoms to fold it under', () => {
    const { cards, sites } = layoutSummary([section('pathologies'), section('anatomy')])

    expect(keysOf(cards)).toEqual(['pathologies', 'anatomy'])
    expect(sites).toBeNull()
  })

  it('appends a section this layout has never heard of rather than dropping it', () => {
    const { cards } = layoutSummary([section('measurements'), section('pathologies')])

    expect(keysOf(cards)).toEqual(['pathologies', 'measurements'])
  })

  it('handles a summary with no sections at all', () => {
    expect(layoutSummary([])).toEqual({ cards: [], sites: null })
  })
})

describe('layoutSummary ordering guarantees', () => {
  it('keeps two unknown sections in the order they arrived', () => {
    const { cards } = layoutSummary([
      section('measurements'),
      section('temporal'),
      section('pathologies'),
    ])

    expect(keysOf(cards)).toEqual(['pathologies', 'measurements', 'temporal'])
  })

  it('folds anatomy and appends an unknown key in the same pass', () => {
    const { cards, sites } = layoutSummary([
      section('anatomy'),
      section('other'),
      section('symptoms'),
      section('pathologies'),
    ])

    expect(keysOf(cards)).toEqual(['pathologies', 'symptoms', 'other'])
    expect(sites?.key).toBe('anatomy')
  })
})
