import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { AnalysisFailure } from '../AnalysisFailure'
import type { StreamFailure } from '../../lib/analysisStream'

const MESSAGE = 'Unable to extract text from the document.'

function renderFailure(
  reason: StreamFailure,
  onRetry = vi.fn(),
  onStartOver = vi.fn()
) {
  return {
    onRetry,
    onStartOver,
    ...render(
      <AnalysisFailure
        message={MESSAGE}
        reason={reason}
        onRetry={onRetry}
        onStartOver={onStartOver}
      />
    ),
  }
}

describe('AnalysisFailure', () => {
  it('announces itself as an alert', () => {
    renderFailure('transport')
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('blames a document rather than the service for an unreadable batch', () => {
    renderFailure('unreadable_batch')
    expect(screen.getByRole('alert')).toHaveTextContent(
      "Aucun résumé n'a pu être établi"
    )
  })

  it('blames the service rather than the documents for a server error', () => {
    renderFailure('server_error')
    expect(screen.getByRole('alert')).toHaveTextContent("L'analyse n'a pas abouti")
  })

  it('names a stream that could not be read at all as its own thing', () => {
    renderFailure('transport')
    expect(screen.getByRole('alert')).toHaveTextContent("L'analyse s'est interrompue")
  })

  it('shows the backend message whole underneath the headline', () => {
    renderFailure('server_error')
    expect(screen.getByRole('alert')).toHaveTextContent(MESSAGE)
  })

  it('retries on request', () => {
    const { onRetry } = renderFailure('unreadable_batch')

    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('starts over on request rather than retrying the same batch', () => {
    const { onStartOver, onRetry } = renderFailure('unreadable_batch')

    fireEvent.click(screen.getByRole('button', { name: "Choisir d'autres documents" }))
    expect(onStartOver).toHaveBeenCalledOnce()
    expect(onRetry).not.toHaveBeenCalled()
  })

  it('falls back to the neutral headline for a reason added later', () => {
    // An alert whose first line is empty tells a clinician less than the
    // generic wording does.
    render(
      <AnalysisFailure
        message="Something failed"
        reason={'cosmic_rays' as never}
        onRetry={() => {}}
        onStartOver={() => {}}
      />
    )

    expect(screen.getByRole('alert')).toHaveTextContent("L'analyse s'est interrompue")
  })
})
