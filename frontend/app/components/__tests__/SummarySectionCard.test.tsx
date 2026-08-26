import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SummarySectionCard } from '../SummarySectionCard'
import type { SummarySection } from '../../types/extraction'

function section(overrides: Partial<SummarySection> = {}): SummarySection {
  return {
    key: 'pathologies',
    heading: 'Pathologies',
    sentence: 'Cirrhose, hypertension portale.',
    findings: ['cirrhose', 'hypertension portale'],
    ...overrides,
  }
}

const SITES = section({
  key: 'anatomy',
  heading: 'Localisations',
  sentence: 'Foie.',
  findings: ['foie', 'veine porte'],
})

describe('SummarySectionCard', () => {
  it('renders one row per finding, not the ready-made sentence', () => {
    render(<SummarySectionCard section={section()} />)

    expect(screen.getByText('cirrhose')).toBeInTheDocument()
    expect(screen.getByText('hypertension portale')).toBeInTheDocument()
    expect(
      screen.queryByText('Cirrhose, hypertension portale.')
    ).not.toBeInTheDocument()
  })

  it('titles the card with the heading the API supplied', () => {
    render(<SummarySectionCard section={section()} />)
    expect(screen.getByRole('heading', { name: 'Pathologies' })).toBeInTheDocument()
  })

  it('renders repeated findings as separate rows', () => {
    // The backend deduplicates, so this should not arrive - but the row key
    // must not depend on that holding.
    render(<SummarySectionCard section={section({ findings: ['fièvre', 'fièvre'] })} />)
    expect(screen.getAllByText('fièvre')).toHaveLength(2)
  })

  it('adds the sites line when one is folded in', () => {
    render(<SummarySectionCard section={section()} sites={SITES} />)
    expect(screen.getByText(/Localisations : foie, veine porte/)).toBeInTheDocument()
  })

  it('omits the sites line when there is none', () => {
    const { container } = render(<SummarySectionCard section={section()} />)
    expect(container.textContent).not.toMatch(/Localisations/)
  })

  it('omits the sites line when the sites section is empty', () => {
    const { container } = render(
      <SummarySectionCard section={section()} sites={section({ key: 'anatomy', heading: 'Localisations', findings: [] })} />
    )
    expect(container.textContent).not.toMatch(/Localisations/)
  })

  it('renders a section with no findings without crashing', () => {
    render(<SummarySectionCard section={section({ findings: [] })} />)
    expect(screen.getByRole('heading', { name: 'Pathologies' })).toBeInTheDocument()
  })
})
