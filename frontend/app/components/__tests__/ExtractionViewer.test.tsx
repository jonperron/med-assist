import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ExtractionViewer from '../ExtractionViewer'

const emptyEntities = {
  patient_info: [],
  anatomy: [],
  symptoms: [],
  examinations: [],
  treatments: [],
  pathologies: [],
  temporal: [],
  measurements: [],
  other: [],
}

const baseData = {
  file_id: '00000000-0000-0000-0000-000000000001',
  text: 'Le patient présente une fièvre.',
  extracted_entities: emptyEntities,
}

describe('ExtractionViewer', () => {
  it('renders the "Extracted Entities" heading', () => {
    render(<ExtractionViewer data={baseData} />)
    expect(screen.getByText('Extracted Entities')).toBeInTheDocument()
  })

  it('displays mapping_info when provided', () => {
    const data = {
      ...baseData,
      mapping_info: { language: 'fr', dataset: 'deft2021', description: 'French NER' },
    }
    render(<ExtractionViewer data={data} />)
    expect(screen.getByText(/deft2021/)).toBeInTheDocument()
  })

  it('does not render empty categories', () => {
    render(<ExtractionViewer data={baseData} />)
    expect(screen.queryByText('Symptoms:')).not.toBeInTheDocument()
  })

  it('renders entities with score when category has data', () => {
    const data = {
      ...baseData,
      extracted_entities: {
        ...emptyEntities,
        symptoms: [{ text: 'fièvre', label: 'SYMP', score: 0.92, start: 0, end: 6 }],
      },
    }
    render(<ExtractionViewer data={data} />)
    expect(screen.getByText(/fièvre/)).toBeInTheDocument()
    expect(screen.getByText('(92%)')).toBeInTheDocument()
  })

  it('does not render the Model line when mapping_info is absent', () => {
    render(<ExtractionViewer data={baseData} />)
    expect(screen.queryByText(/Model:/)).not.toBeInTheDocument()
  })

  it('filters out entities whose text is a single character', () => {
    const data = {
      ...baseData,
      extracted_entities: {
        ...emptyEntities,
        symptoms: [{ text: 'X', label: 'SYMP', score: 0.99, start: 0, end: 1 }],
      },
    }
    render(<ExtractionViewer data={data} />)
    expect(screen.queryByText('Symptoms:')).not.toBeInTheDocument()
    expect(screen.queryByText(/X/)).not.toBeInTheDocument()
  })

  it('renders multiple filled categories independently', () => {
    const data = {
      ...baseData,
      extracted_entities: {
        ...emptyEntities,
        symptoms: [{ text: 'fièvre', label: 'SYMP', score: 0.85, start: 0, end: 6 }],
        treatments: [{ text: 'paracétamol', label: 'TREA', score: 0.78, start: 10, end: 21 }],
      },
    }
    render(<ExtractionViewer data={data} />)
    expect(screen.getByText('Symptoms:')).toBeInTheDocument()
    expect(screen.getByText('Treatments:')).toBeInTheDocument()
    expect(screen.getByText(/fièvre/)).toBeInTheDocument()
    expect(screen.getByText(/paracétamol/)).toBeInTheDocument()
  })

  it('rounds score percentages correctly (0.925 → 93%)', () => {
    const data = {
      ...baseData,
      extracted_entities: {
        ...emptyEntities,
        pathologies: [{ text: 'diabète', label: 'PATH', score: 0.925, start: 0, end: 7 }],
      },
    }
    render(<ExtractionViewer data={data} />)
    expect(screen.getByText('(93%)')).toBeInTheDocument()
  })
})
