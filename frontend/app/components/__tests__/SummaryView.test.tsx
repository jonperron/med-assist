import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { SummaryView } from '../SummaryView'
import type { ClinicalSummary } from '../../types/extraction'
import type { SelectedDocument } from '../../lib/documentSelection'

function summary(overrides: Partial<ClinicalSummary> = {}): ClinicalSummary {
  return {
    patient: 'Patient, 67 ans, homme.',
    sections: [
      {
        key: 'pathologies',
        heading: 'Pathologies',
        sentence: 'Cirrhose, carcinome hépatocellulaire.',
        findings: [
          { text: 'cirrhose', documents: [0, 1] },
          { text: 'carcinome hépatocellulaire', documents: [1] },
        ],
      },
      {
        key: 'symptoms',
        heading: 'Signes et symptômes',
        sentence: 'Ictère.',
        findings: [{ text: 'ictère', documents: [1] }],
      },
      {
        key: 'anatomy',
        heading: 'Localisations',
        sentence: 'Foie, veine porte.',
        findings: [
          { text: 'foie', documents: [0] },
          { text: 'veine porte', documents: [0, 1] },
        ],
      },
    ],
    document_count: 3,
    date_range: null,
    empty: false,
    ...overrides,
  }
}

function documents(names: string[] = ['lettre-adressage.pdf']): SelectedDocument[] {
  return names.map((name, index) => ({
    id: `document-${index}`,
    file: new File(['content'], name, { type: 'application/pdf' }),
  }))
}

function sourceChips() {
  return within(screen.getByRole('list', { name: 'Lu dans' }))
}

function renderSummary(
  overrides: Partial<ClinicalSummary> = {},
  onStartOver = vi.fn()
) {
  return {
    onStartOver,
    ...render(
      <SummaryView
        summary={summary(overrides)}
        documents={documents(['lettre-adressage.pdf', 'compte-rendu-ecg.pdf'])}
        onStartOver={onStartOver}
      />
    ),
  }
}

describe('SummaryView', () => {
  it('titles the summary with how many documents it read', () => {
    renderSummary()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Résumé de 3 documents'
    )
  })

  it('says one document without pluralising', () => {
    renderSummary({ document_count: 1 })
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      "Résumé d'un document"
    )
  })

  it('opens with the patient line', () => {
    renderSummary()
    expect(screen.getByText('Patient, 67 ans, homme.')).toBeInTheDocument()
  })

  it('omits the patient line when there is no demographic mention', () => {
    const { container } = renderSummary({ patient: null })
    expect(container.textContent).not.toMatch(/Patient,/)
  })

  it('names the documents the summary was read from', () => {
    renderSummary()
    expect(sourceChips().getByText('Lettre adressage')).toBeInTheDocument()
    expect(sourceChips().getByText('Compte rendu ecg')).toBeInTheDocument()
  })

  it('names the document behind a finding only one of them carried', () => {
    renderSummary()
    // `carcinome hépatocellulaire` came from documents: [1].
    const row = screen.getByText('carcinome hépatocellulaire').closest('li')
    expect(row).toHaveTextContent('Compte rendu ecg')
  })

  it('counts the documents behind a finding several of them agree on', () => {
    renderSummary()
    const row = screen.getByText('cirrhose').closest('li')
    expect(row).toHaveTextContent('2 documents')
  })

  it('lays each section out as a heading and its findings', () => {
    renderSummary()
    expect(screen.getByRole('heading', { name: 'Pathologies' })).toBeInTheDocument()
    expect(screen.getByText('cirrhose')).toBeInTheDocument()
    expect(screen.getByText('carcinome hépatocellulaire')).toBeInTheDocument()
  })

  it('folds the sites into a quiet line rather than a section of their own', () => {
    renderSummary()
    expect(
      screen.queryByRole('heading', { name: 'Localisations' })
    ).not.toBeInTheDocument()
    expect(screen.getByText(/Localisations : foie, veine porte/)).toBeInTheDocument()
  })

  it('shows no score, percentage, model or timing anywhere', () => {
    const { container } = renderSummary()
    expect(container.textContent).not.toMatch(/%/)
    expect(container.textContent).not.toMatch(/score|confiance|modèle|ms\b/i)
  })

  it('says so rather than rendering an empty page', () => {
    renderSummary({ empty: true, sections: [], patient: null, document_count: 2 })
    expect(screen.getByRole('status')).toHaveTextContent(
      /Aucun élément clinique.*ces documents/
    )
  })

  it('says nothing was found when the only finding was a patient line', () => {
    // The backend sets `empty` false whenever a patient line exists, so this
    // arrives as a non-empty summary carrying no sections at all.
    renderSummary({ empty: false, sections: [], document_count: 2 })

    expect(screen.getByRole('status')).toHaveTextContent(/Aucun élément clinique/)
  })

  it('names the source documents in the printed copy', () => {
    const { container } = renderSummary()
    const chip = sourceChips().getByText('Lettre adressage')

    expect(container.querySelector('[data-print="hide"]')).not.toContainElement(chip)
  })

  it('starts over on request', () => {
    const onStartOver = vi.fn()
    renderSummary({}, onStartOver)

    fireEvent.click(screen.getByRole('button', { name: 'Nouveau résumé' }))
    expect(onStartOver).toHaveBeenCalledOnce()
  })

  it('prints the summary on request', () => {
    const print = vi.fn()
    vi.stubGlobal('print', print)
    renderSummary()

    fireEvent.click(screen.getByRole('button', { name: 'Imprimer' }))
    expect(print).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })
})
