import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SummarySectionCard } from '../SummarySectionCard'
import type { SummarySection } from '../../types/extraction'
import type { SelectedDocument } from '../../lib/documentSelection'

function section(overrides: Partial<SummarySection> = {}): SummarySection {
  return {
    key: 'pathologies',
    heading: 'Pathologies',
    sentence: 'Cirrhose, hypertension portale.',
    findings: [
      { text: 'cirrhose', documents: [0] },
      { text: 'hypertension portale', documents: [0, 1] },
    ],
    ...overrides,
  }
}

const SITES = section({
  key: 'anatomy',
  heading: 'Localisations',
  sentence: 'Foie.',
  findings: [
    { text: 'foie', documents: [0] },
    { text: 'veine porte', documents: [1] },
  ],
})

function documents(
  names: string[] = ['lettre-adressage.pdf', 'compte-rendu-ecg.pdf']
): SelectedDocument[] {
  return names.map((name, index) => ({
    id: `document-${index}`,
    file: new File(['content'], name, { type: 'application/pdf' }),
  }))
}

function renderCard(
  overrides: Partial<SummarySection> = {},
  sites: SummarySection | null = null,
  selected: SelectedDocument[] = documents()
) {
  return render(
    <SummarySectionCard section={section(overrides)} documents={selected} sites={sites} />
  )
}

describe('SummarySectionCard', () => {
  it('renders one row per finding, not the ready-made sentence', () => {
    renderCard()

    expect(screen.getByText('cirrhose')).toBeInTheDocument()
    expect(screen.getByText('hypertension portale')).toBeInTheDocument()
    expect(
      screen.queryByText('Cirrhose, hypertension portale.')
    ).not.toBeInTheDocument()
  })

  it('titles the card with the heading the API supplied', () => {
    renderCard()
    expect(screen.getByRole('heading', { name: 'Pathologies' })).toBeInTheDocument()
  })

  it('names the single document a finding came from', () => {
    renderCard()
    expect(screen.getByText('Lettre adressage')).toBeInTheDocument()
  })

  it('counts the documents when several agree on a finding', () => {
    renderCard()
    expect(screen.getByText('2 documents')).toBeInTheDocument()
  })

  it('leaves the row unlabelled when no index resolves to a selected document', () => {
    // Page state and the response disagreeing is not a reason to name the
    // wrong document.
    const { container } = renderCard({
      findings: [{ text: 'cirrhose', documents: [7] }],
    })

    expect(screen.getByText('cirrhose')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/Lettre adressage|documents/)
  })

  it('renders repeated findings as separate rows', () => {
    // The backend deduplicates, so this should not arrive - but the row key
    // must not depend on that holding.
    renderCard({
      findings: [
        { text: 'fièvre', documents: [0] },
        { text: 'fièvre', documents: [1] },
      ],
    })
    expect(screen.getAllByText('fièvre')).toHaveLength(2)
  })

  it('adds the sites line when one is folded in', () => {
    renderCard({}, SITES)
    expect(screen.getByText(/Localisations : foie, veine porte/)).toBeInTheDocument()
  })

  it('omits the sites line when there is none', () => {
    const { container } = renderCard()
    expect(container.textContent).not.toMatch(/Localisations/)
  })

  it('omits the sites line when the sites section is empty', () => {
    const { container } = renderCard(
      {},
      section({ key: 'anatomy', heading: 'Localisations', findings: [] })
    )
    expect(container.textContent).not.toMatch(/Localisations/)
  })

  it('renders a section with no findings without crashing', () => {
    renderCard({ findings: [] })
    expect(screen.getByRole('heading', { name: 'Pathologies' })).toBeInTheDocument()
  })

  it('shows no score or offset beside a finding', () => {
    const { container } = renderCard()
    expect(container.textContent).not.toMatch(/%|score|0\.\d/i)
  })
})
