import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PrivacyBadge } from '../PrivacyBadge'
import { UnsecuredDeploymentNotice } from '../UnsecuredDeploymentNotice'
import { UnsecuredDeploymentProvider } from '../../lib/deploymentContext'

function noticeText(): string {
  return screen.getByRole('alert').textContent ?? ''
}

describe('UnsecuredDeploymentNotice', () => {
  it('tells the clinician not to submit real documents', () => {
    // The only sentence that changes what the person about to use this does.
    render(<UnsecuredDeploymentNotice />)

    expect(noticeText()).toMatch(/n'y déposez aucun document réel/i)
  })

  it('says the deployment is open and that a third party may read what is sent', () => {
    render(<UnsecuredDeploymentNotice />)

    expect(noticeText()).toMatch(/n'importe qui peut y accéder/i)
    expect(noticeText()).toMatch(/lus par un tiers/i)
  })

  it('is announced rather than left to be noticed', () => {
    // `alert`, not `status`: it is a thing to know before touching anything.
    render(<UnsecuredDeploymentNotice />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('names no configuration', () => {
    // A clinician needs a sentence, not a threat model - and the interface says
    // nothing about how the deployment is put together to anyone who reaches it.
    expect(noticeTextAfterRender()).not.toMatch(/\b(token|proxy|CORS|API|port)\b/i)
  })
})

function noticeTextAfterRender(): string {
  render(<UnsecuredDeploymentNotice />)
  return noticeText()
}

describe('PrivacyBadge on an open deployment', () => {
  it('claims the documents stay on this machine by default', () => {
    render(<PrivacyBadge />)

    expect(screen.getByText('Reste sur cette machine')).toBeInTheDocument()
  })

  it('makes no claim at all when the deployment is open', () => {
    // The claim reads as "stays on mine", which is wrong on a published
    // address - and it would sit directly under a banner saying the opposite.
    render(
      <UnsecuredDeploymentProvider unsecured>
        <PrivacyBadge />
      </UnsecuredDeploymentProvider>
    )

    expect(screen.queryByText('Reste sur cette machine')).not.toBeInTheDocument()
  })
})
