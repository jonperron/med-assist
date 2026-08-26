import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { DocumentList } from '../DocumentList'
import type { SelectedDocument } from '../../lib/documentSelection'

function documents(names: string[]): SelectedDocument[] {
  return names.map((name, index) => ({
    id: `document-${index}`,
    file: new File(['content'], name, { type: 'application/pdf' }),
  }))
}

describe('DocumentList', () => {
  it('renders nothing before a document is chosen', () => {
    const { container } = render(
      <DocumentList documents={[]} onRemove={vi.fn()} onRemoveAll={vi.fn()} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('counts the documents that are ready', () => {
    render(
      <DocumentList
        documents={documents(['a.pdf', 'b.pdf'])}
        onRemove={vi.fn()}
        onRemoveAll={vi.fn()}
      />
    )
    expect(screen.getByText('2 documents prêts')).toBeInTheDocument()
  })

  it('counts one document without pluralising', () => {
    render(
      <DocumentList
        documents={documents(['a.pdf'])}
        onRemove={vi.fn()}
        onRemoveAll={vi.fn()}
      />
    )
    expect(screen.getByText('1 document prêt')).toBeInTheDocument()
  })

  it('shows the filename as chosen, not a prettified one', () => {
    render(
      <DocumentList
        documents={documents(['lettre-adressage.pdf'])}
        onRemove={vi.fn()}
        onRemoveAll={vi.fn()}
      />
    )
    expect(screen.getByText('lettre-adressage.pdf')).toBeInTheDocument()
  })

  it('removes one named document', () => {
    const onRemove = vi.fn()
    render(
      <DocumentList
        documents={documents(['a.pdf', 'b.pdf'])}
        onRemove={onRemove}
        onRemoveAll={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Retirer b.pdf' }))
    expect(onRemove).toHaveBeenCalledWith('document-1')
  })

  it('removes them all at once', () => {
    const onRemoveAll = vi.fn()
    render(
      <DocumentList
        documents={documents(['a.pdf'])}
        onRemove={vi.fn()}
        onRemoveAll={onRemoveAll}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Tout retirer' }))
    expect(onRemoveAll).toHaveBeenCalledOnce()
  })
})
