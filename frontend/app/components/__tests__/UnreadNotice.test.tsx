import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UnreadNotice } from '../UnreadNotice'
import type { UnreadDocument } from '../../lib/unreadDocuments'

function noText(...names: string[]): UnreadDocument[] {
  return names.map(name => ({ name, reason: 'no_text' as const }))
}

describe('UnreadNotice', () => {
  it('renders nothing when every document was read', () => {
    const { container } = render(<UnreadNotice documents={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says one document was skipped without pluralising', () => {
    render(<UnreadNotice documents={noText('Scan illisible')} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      "Un document n'a pas pu être lu"
    )
  })

  it('counts several skipped documents', () => {
    render(<UnreadNotice documents={noText('Scan illisible', 'Fax')} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      "2 documents n'ont pas pu être lus"
    )
  })

  it('names every document it is reporting', () => {
    render(<UnreadNotice documents={noText('Scan illisible', 'Fax')} />)
    expect(screen.getByRole('status')).toHaveTextContent(/Scan illisible, Fax/)
  })

  it('says the summary does not contain them', () => {
    render(<UnreadNotice documents={noText('Scan illisible')} />)
    expect(screen.getByRole('status')).toHaveTextContent(/ne les contient pas/)
  })

  it('gives no scan-specific advice for a reason this build does not know', () => {
    // `UnreadableReason` is documented as a set that will grow. Advice for
    // today's only member would become confidently wrong advice.
    render(<UnreadNotice documents={[{ name: 'Scan illisible', reason: null }]} />)

    expect(screen.getByRole('status')).not.toHaveTextContent(/image scannée/)
    expect(screen.getByRole('status')).toHaveTextContent(/ne les contient pas/)
  })

  it('stays in the printed copy', () => {
    const { container } = render(<UnreadNotice documents={noText('Scan illisible')} />)
    expect(container.querySelector('[data-print="hide"]')).toBeNull()
  })
})
