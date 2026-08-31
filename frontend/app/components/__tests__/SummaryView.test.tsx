import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { SummaryView } from '../SummaryView'
import type {
  AnalysisResponse,
  AnalyzedDocument,
  ClinicalSummary,
} from '../../types/extraction'
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

function analyzed(
  dates: (string | null)[],
  read: boolean[] = dates.map(() => true)
): AnalyzedDocument[] {
  return dates.map((document_date, index) => ({
    patient_info: [],
    anatomy: [],
    symptoms: [],
    examinations: [],
    treatments: [],
    pathologies: [],
    temporal: [],
    measurements: [],
    other: [],
    read: read[index] ?? true,
    unreadable_reason: read[index] === false ? ('no_text' as const) : null,
    document_date,
  }))
}

function response(
  overrides: Partial<ClinicalSummary> = {},
  dates: (string | null)[] = [null, null],
  read?: boolean[]
): AnalysisResponse {
  return {
    summary: summary(overrides),
    documents: analyzed(dates, read),
  }
}

function sourceChips() {
  return within(screen.getByRole('list', { name: 'Lu dans' }))
}

function renderSummary(
  overrides: Partial<ClinicalSummary> = {},
  onStartOver = vi.fn(),
  dates: (string | null)[] = [null, null],
  read?: boolean[]
) {
  return {
    onStartOver,
    ...render(
      <SummaryView
        analysis={response(overrides, dates, read)}
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

  it('places the summary in time with the span the documents cover', () => {
    renderSummary({ date_range: { start: '2025-03-04', end: '2025-04-02' } })
    expect(screen.getByText('du 4 mars au 2 avril 2025')).toBeInTheDocument()
  })

  it('says nothing about time when no document could be dated', () => {
    const { container } = renderSummary({ date_range: null })
    expect(container.textContent).not.toMatch(/du .* au /)
  })

  it('dates each source chip from the document itself', () => {
    renderSummary({}, vi.fn(), ['2025-03-04', null])

    const chips = sourceChips()
    expect(chips.getByText('4 mars 2025')).toBeInTheDocument()
    // The undated one is left undated rather than borrowing its neighbour.
    expect(chips.getAllByRole('listitem')[1]).not.toHaveTextContent(/2025/)
  })

  it('says which document the batch could not read', () => {
    renderSummary({ document_count: 1 }, vi.fn(), [null, null], [true, false])

    const notice = screen.getByRole('status')
    expect(notice).toHaveTextContent("Un document n'a pas pu être lu")
    expect(notice).toHaveTextContent('Compte rendu ecg')
  })

  it('marks the unread document in the source chips instead of hiding it', () => {
    renderSummary({ document_count: 1 }, vi.fn(), [null, null], [true, false])

    const chips = sourceChips().getAllByRole('listitem')
    expect(chips).toHaveLength(2)
    expect(chips[1]).toHaveTextContent('non lu')
  })

  it('says nothing about unread documents when the whole batch was read', () => {
    const { container } = renderSummary()
    expect(container.textContent).not.toMatch(/n'a pas pu être lu|non lu/)
  })

  it('strips an override out of the patient line', () => {
    // It is built from spans the model marked, so it is document text too.
    renderSummary({ patient: 'Patient, 67\u202Eans, homme.' })
    expect(screen.getByText('Patient, 67ans, homme.')).toBeInTheDocument()
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

    // Every print-hidden region, not the first one. `querySelector` returned
    // the header, which the chip was never inside, so the assertion held for
    // a reason that had nothing to do with what it was checking.
    const hidden = container.querySelectorAll('[data-print="hide"]')
    expect(hidden.length).toBeGreaterThan(0)
    hidden.forEach(region => expect(region).not.toContainElement(chip))
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

  it('carries the footer', () => {
    // The screen a clinician spends the longest on is the one where the
    // question "where did my documents go" is most likely to be asked.
    renderSummary()
    expect(screen.getByRole('contentinfo')).toHaveTextContent(
      /Aucun document n'est enregistré sur le serveur/
    )
  })
})
