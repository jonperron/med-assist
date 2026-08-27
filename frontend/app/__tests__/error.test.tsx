import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import AnalysisBoundary from '../error'

describe('AnalysisBoundary', () => {
  it('says the display failed without saying what was in it', () => {
    render(<AnalysisBoundary reset={vi.fn()} />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      /L'affichage du résumé a échoué/
    )
  })

  it('shows nothing about the error itself', () => {
    // The offending value on these screens is patient-derived.
    const { container } = render(<AnalysisBoundary reset={vi.fn()} />)

    expect(container.textContent).not.toMatch(/Error|undefined|TypeError|digest|at /)
  })

  it('says nothing was kept', () => {
    render(<AnalysisBoundary reset={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent(/Rien n'a été conservé/)
  })

  it('offers a way back', () => {
    const reset = vi.fn()
    render(<AnalysisBoundary reset={reset} />)

    fireEvent.click(screen.getByRole('button', { name: 'Recommencer' }))
    expect(reset).toHaveBeenCalledOnce()
  })
})
