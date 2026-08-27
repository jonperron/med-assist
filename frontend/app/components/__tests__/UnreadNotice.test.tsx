import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UnreadNotice } from '../UnreadNotice'

describe('UnreadNotice', () => {
  it('renders nothing when every document was read', () => {
    const { container } = render(<UnreadNotice names={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says one document was skipped without pluralising', () => {
    render(<UnreadNotice names={['Scan illisible']} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      "Un document n'a pas pu être lu"
    )
  })

  it('counts several skipped documents', () => {
    render(<UnreadNotice names={['Scan illisible', 'Fax']} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      "2 documents n'ont pas pu être lus"
    )
  })

  it('names every document it is reporting', () => {
    render(<UnreadNotice names={['Scan illisible', 'Fax']} />)
    expect(screen.getByRole('status')).toHaveTextContent(/Scan illisible, Fax/)
  })

  it('says the summary does not contain them', () => {
    render(<UnreadNotice names={['Scan illisible']} />)
    expect(screen.getByRole('status')).toHaveTextContent(/ne les contient pas/)
  })

  it('stays in the printed copy', () => {
    const { container } = render(<UnreadNotice names={['Scan illisible']} />)
    expect(container.querySelector('[data-print="hide"]')).toBeNull()
  })
})
