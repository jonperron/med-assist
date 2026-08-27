import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ReadingProgress } from '../ReadingProgress'
import type { DocumentReadState } from '../../lib/readingState'
import type { SelectedDocument } from '../../lib/documentSelection'

function documents(count: number): SelectedDocument[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `document-${index}`,
    file: new File(['content'], `report${index}.txt`, { type: 'text/plain' }),
  }))
}

function renderProgress(states: DocumentReadState[], finished: number) {
  return render(
    <ReadingProgress
      documents={documents(states.length)}
      states={states}
      finished={finished}
    />
  )
}

describe('ReadingProgress', () => {
  it('counts how many of how many are done', () => {
    renderProgress(['read', 'reading', 'pending'], 1)
    expect(screen.getByText('1 sur 3')).toBeInTheDocument()
  })

  it('says one document without pluralising', () => {
    renderProgress(['reading'], 0)
    expect(screen.getByText('Lecture du document')).toBeInTheDocument()
  })

  it('fills the bar in proportion to what is done', () => {
    const { container } = renderProgress(['read', 'read', 'pending', 'pending'], 2)
    const bar = container.querySelector('[style*="width"]') as HTMLElement

    expect(bar.style.width).toBe('50%')
  })

  it('leaves the bar empty before anything has landed', () => {
    const { container } = renderProgress(['reading', 'pending'], 0)
    const bar = container.querySelector('[style*="width"]') as HTMLElement

    expect(bar.style.width).toBe('0%')
  })

  it('marks a document the batch could not read', () => {
    renderProgress(['unread', 'reading'], 1)
    const rows = within(screen.getByRole('status')).getAllByRole('listitem')

    expect(rows[0]).toHaveTextContent('non lu')
    expect(rows[1]).not.toHaveTextContent('non lu')
  })

  it('names every document from the selection', () => {
    renderProgress(['read', 'reading'], 1)

    expect(screen.getByText('report0.txt')).toBeInTheDocument()
    expect(screen.getByText('report1.txt')).toBeInTheDocument()
  })

  it('falls back to pending for a state the batch has not reached', () => {
    // A response shorter than the batch must not crash the card.
    renderProgress([], 0)
    expect(screen.getByText('0 sur 0')).toBeInTheDocument()
  })

  it('shows no timing, percentage or model name', () => {
    const { container } = renderProgress(['read', 'reading'], 1)

    expect(container.textContent).not.toMatch(/%|secondes|ms\b|modèle/i)
  })

  it('announces itself politely rather than interrupting', () => {
    renderProgress(['reading'], 0)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
