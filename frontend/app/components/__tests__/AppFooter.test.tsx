import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppFooter } from '../AppFooter'
import { version } from '../../../package.json'

describe('AppFooter', () => {
  it('shows the version the manifest declares', () => {
    // Read from the manifest rather than written out, so a release bump does
    // not have to be made in two places. What this proves is the wiring:
    // `vitest.config.ts` and `next.config.ts` both inject the same value, and
    // a footer that fell back to `dev` would fail here.
    render(<AppFooter />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(`Med-Assist v${version}`)
  })

  it('does not fall back to the placeholder version', () => {
    render(<AppFooter />)
    expect(screen.getByRole('contentinfo')).not.toHaveTextContent('vdev')
  })

  it('points the issue link at the public repository', () => {
    render(<AppFooter />)
    const link = screen.getByRole('link', { name: /Signaler un problème/ })
    expect(link).toHaveAttribute('href', 'https://github.com/jonperron/med-assist/issues')
  })

  it('says in the link name that it opens a tab', () => {
    // The one place this interface takes the clinician somewhere else. A tab
    // change that is only discovered after the click is the accessibility
    // failure; naming it is what makes it not one.
    render(<AppFooter />)
    expect(
      screen.getByRole('link', { name: /Signaler un problème \(nouvel onglet\)/ })
    ).toBeInTheDocument()
  })

  it('opens the issue link without handing the tab to it', () => {
    // The one navigation this interface offers off-origin. `noopener` keeps
    // the opened tab from reaching back through `window.opener`, `noreferrer`
    // keeps the address of the page a clinician was on out of the request.
    render(<AppFooter />)
    const link = screen.getByRole('link', { name: /Signaler un problème/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('states that nothing is kept on the server', () => {
    render(<AppFooter />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(
      /Aucun document n'est enregistré sur le serveur/
    )
  })

  it('describes the storage as temporary rather than as absent', () => {
    // The backend does spool a large multipart part to disk. Claiming the
    // documents never touch one would be a stronger promise than the service
    // keeps, and this footer is the place a clinician would read it.
    render(<AppFooter />)
    expect(screen.getByRole('contentinfo')).toHaveTextContent(/stockage temporaire/)
  })

  it('leaves the printed copy', () => {
    // A summary going into a patient file is about the patient. A version
    // number and an issue tracker are about this software.
    const { container } = render(<AppFooter />)
    expect(container.querySelector('[data-print="hide"]')).not.toBeNull()
  })
})
