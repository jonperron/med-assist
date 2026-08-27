import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import SummaryView from '../SummaryView'
import type { ClinicalSummary } from '../../types/extraction'

function summary(overrides: Partial<ClinicalSummary> = {}): ClinicalSummary {
  return {
    patient: 'Patient, 67 ans, homme.',
    sections: [
      {
        key: 'pathologies',
        heading: 'Pathologies',
        sentence: 'Cirrhose, carcinome hépatocellulaire.',
        findings: [
          { text: 'cirrhose', documents: [0, 2] },
          { text: 'carcinome hépatocellulaire', documents: [1] },
        ],
      },
    ],
    document_count: 3,
    empty: false,
    ...overrides,
  }
}

describe('SummaryView', () => {
  it('opens with the patient line', () => {
    render(<SummaryView summary={summary()} />)
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('renders each section as a heading and a sentence', () => {
    render(<SummaryView summary={summary()} />)
    expect(screen.getByText('Pathologies')).toBeInTheDocument()
    expect(
      screen.getByText('Cirrhose, carcinome hépatocellulaire.')
    ).toBeInTheDocument()
  })

  it('shows no percentage or confidence anywhere', () => {
    const { container } = render(<SummaryView summary={summary()} />)
    expect(container.textContent).not.toMatch(/%/)
    expect(container.textContent).not.toMatch(/score|confiance/i)
  })

  it('says how many documents it read', () => {
    render(<SummaryView summary={summary()} />)
    expect(screen.getByText(/3 documents/)).toBeInTheDocument()
  })

  it('says one document without pluralising', () => {
    render(<SummaryView summary={summary({ document_count: 1 })} />)
    expect(screen.getByText(/1 document\./)).toBeInTheDocument()
  })

  it('omits the patient line when there is no demographic mention', () => {
    const { container } = render(<SummaryView summary={summary({ patient: null })} />)
    expect(container.textContent).not.toMatch(/Patient,/)
    expect(screen.getByText('Pathologies')).toBeInTheDocument()
  })

  it('says so rather than rendering an empty page', () => {
    render(
      <SummaryView
        summary={summary({ empty: true, sections: [], patient: null, document_count: 2 })}
      />
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      /Aucun élément clinique.*ces documents/
    )
  })
})
