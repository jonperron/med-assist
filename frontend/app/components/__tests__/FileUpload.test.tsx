import { describe, expect, it, vi } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import FileUpload from '../FileUpload'

function pdf(name = 'report.pdf') {
  return new File(['content'], name, { type: 'application/pdf' })
}

function input(container: HTMLElement) {
  return container.querySelector('input[type="file"]') as HTMLInputElement
}

describe('FileUpload', () => {
  it('renders a file input', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    expect(input(container)).toBeInTheDocument()
  })

  it('accepts .pdf, .docx and .txt files', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    expect(input(container).accept).toBe('.pdf,.docx,.txt')
  })

  it('takes several documents at once', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    expect(input(container).multiple).toBe(true)
  })

  it('hands every selected document to the caller', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)
    const files = [pdf('a.pdf'), pdf('b.pdf')]

    fireEvent.change(input(container), { target: { files } })

    expect(onUpload).toHaveBeenCalledOnce()
    expect(onUpload).toHaveBeenCalledWith(files)
  })

  it('does not call onUpload when nothing is selected', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)

    fireEvent.change(input(container), { target: { files: [] } })

    expect(onUpload).not.toHaveBeenCalled()
  })

  it('refuses the whole selection when one document is not supported', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)
    const files = [pdf(), new File(['x'], 'notes.exe', { type: 'application/exe' })]

    fireEvent.change(input(container), { target: { files } })

    // Filtering the bad one out would summarise fewer documents than selected,
    // without saying so.
    expect(onUpload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/Type de fichier invalide/)
  })

  it('refuses a selection larger than the backend batch cap', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)
    const files = Array.from({ length: 21 }, (_, index) => pdf(`doc${index}.pdf`))

    fireEvent.change(input(container), { target: { files } })

    expect(onUpload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/Maximum : 20/)
  })

  it('can be disabled while an analysis is running', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} disabled />)
    expect(input(container).disabled).toBe(true)
  })
})
