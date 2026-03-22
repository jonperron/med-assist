import { describe, expect, it, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import FileUpload from '../FileUpload'

describe('FileUpload', () => {
  it('renders a file input', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).toBeInTheDocument()
  })

  it('accepts .pdf, .docx and .txt files', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.accept).toBe('.pdf,.docx,.txt')
  })

  it('calls onUpload when a file is selected', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['content'], 'report.pdf', { type: 'application/pdf' })
    fireEvent.change(input, { target: { files: [file] } })
    expect(onUpload).toHaveBeenCalledOnce()
    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('does not call onUpload when no file is selected', () => {
    const onUpload = vi.fn()
    const { container } = render(<FileUpload onUpload={onUpload} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [] } })
    expect(onUpload).not.toHaveBeenCalled()
  })

  it('does not have the multiple attribute — only one file at a time', () => {
    const { container } = render(<FileUpload onUpload={vi.fn()} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.multiple).toBe(false)
  })
})
