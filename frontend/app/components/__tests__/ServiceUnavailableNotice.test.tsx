import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ServiceUnavailableNotice } from '../ServiceUnavailableNotice'

function noticeText(): string {
  return screen.getByRole('status', { name: 'État du service' }).textContent ?? ''
}

describe('ServiceUnavailableNotice', () => {
  it('says the service is unavailable when it has refused', () => {
    render(<ServiceUnavailableNotice reason="unavailable" />)

    expect(noticeText()).toContain("Le service n'est pas disponible")
  })

  it('says only that nothing answered when the service could not be reached', () => {
    // Different situation, different sentence: one is a wait, the other is
    // somebody else's problem, and claiming the service refused would be a
    // statement this client cannot support.
    render(<ServiceUnavailableNotice reason="unreachable" />)

    expect(noticeText()).toContain('Med-Assist ne répond pas')
  })

  it('tells the clinician the screen recovers on its own while waiting', () => {
    // Otherwise the move a clinician makes is to reload, which does nothing the
    // poll is not already doing.
    render(<ServiceUnavailableNotice reason="unavailable" />)

    expect(noticeText()).toMatch(/se met à jour tout seul/)
  })

  it('says an analysis may still be worth trying when nothing answered', () => {
    // The submit button is left enabled in this state, so the copy has to
    // account for a control the other variant does not offer.
    render(<ServiceUnavailableNotice reason="unreachable" />)

    expect(noticeText()).toMatch(/tout de même/)
  })

  it('announces politely rather than interrupting', () => {
    // This is the state of the machine on arrival, not the result of something
    // the clinician just did.
    render(<ServiceUnavailableNotice reason="unavailable" />)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'État du service' })).toBeInTheDocument()
  })

  it('carries a name, because it is not the only status region on the screen', () => {
    // Three other components use role="status". Unnamed, a screen reader
    // announces two polite regions with nothing to tell them apart.
    render(<ServiceUnavailableNotice reason="unavailable" />)

    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'État du service')
  })

  it.each(['unavailable', 'unreachable'] as const)(
    'names nothing about how the service works (%s)',
    reason => {
      // The interface carries no model name, no version, no timing and no
      // configuration anywhere, and a failure is not the place to start.
      render(<ServiceUnavailableNotice reason={reason} />)

      expect(noticeText()).not.toMatch(
        /mod[eè]le|model|NER|weights|poids|503|volume|docker/i
      )
    }
  )

  it.each(['unavailable', 'unreachable'] as const)(
    'blames nothing the clinician has done (%s)',
    reason => {
      render(<ServiceUnavailableNotice reason={reason} />)

      expect(noticeText()).not.toMatch(/document.{0,20}(illisible|refus)|votre fichier/i)
    }
  )
})
