import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { FileDropzone } from '../FileDropzone'

function fileInput(): HTMLInputElement {
  return document.querySelector('input[type="file"]') as HTMLInputElement
}

const PDF = new File(['content'], 'lettre.pdf', { type: 'application/pdf' })

describe('FileDropzone', () => {
  it('hands over the chosen documents', () => {
    const onAdd = vi.fn()
    render(<FileDropzone onAdd={onAdd} />)

    fireEvent.change(fileInput(), { target: { files: [PDF] } })
    expect(onAdd).toHaveBeenCalledWith([PDF])
  })

  it('clears the input so the same document can be chosen twice', () => {
    const onAdd = vi.fn()
    render(<FileDropzone onAdd={onAdd} />)

    fireEvent.change(fileInput(), { target: { files: [PDF] } })
    expect(fileInput().value).toBe('')
  })

  it('says nothing when the selection is empty', () => {
    const onAdd = vi.fn()
    render(<FileDropzone onAdd={onAdd} />)

    fireEvent.change(fileInput(), { target: { files: [] } })
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('hands over dropped documents', () => {
    const onAdd = vi.fn()
    const { container } = render(<FileDropzone onAdd={onAdd} />)

    fireEvent.drop(container.firstChild as HTMLElement, {
      dataTransfer: { files: [PDF] },
    })
    expect(onAdd).toHaveBeenCalledWith([PDF])
  })

  it('ignores a drop while an analysis is running', () => {
    const onAdd = vi.fn()
    const { container } = render(<FileDropzone onAdd={onAdd} disabled />)

    fireEvent.drop(container.firstChild as HTMLElement, {
      dataTransfer: { files: [PDF] },
    })
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('labels the input for a screen reader', () => {
    render(<FileDropzone onAdd={vi.fn()} />)
    expect(screen.getByLabelText(/Documents à résumer/)).toBe(fileInput())
  })
})
