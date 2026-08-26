'use client'

import { useRef, useState } from 'react'
import { Icon } from './Icon'

interface Props {
  onAdd: (files: File[]) => void
}

export function FileDropzone({ onAdd }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (files.length > 0) onAdd(files)
    // Cleared so selecting the same document twice still fires a change.
    event.target.value = ''
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)

    const files = Array.from(event.dataTransfer.files ?? [])
    if (files.length > 0) onAdd(files)
  }

  return (
    <div
      onDragOver={event => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center gap-[18px] rounded-[10px] border border-dashed px-8 py-10 transition-colors ${
        dragging ? 'border-accent bg-accent-tint' : 'border-edge bg-surface'
      }`}
    >
      <Icon name="upload" size={30} strokeWidth={1.4} className="text-accent" />
      <span className="text-lg font-medium text-ink">Déposez les documents ici</span>

      <label htmlFor="documents" className="sr-only">
        Documents à résumer (PDF, DOCX ou TXT)
      </label>
      <input
        id="documents"
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt"
        onChange={handleChange}
        className="sr-only"
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="h-11 cursor-pointer rounded-lg border border-edge bg-surface px-[22px] text-sm font-semibold text-ink hover:bg-paper"
      >
        Choisir des fichiers
      </button>

      <span className="text-[13px] text-ink-muted">PDF, DOCX ou TXT</span>
    </div>
  )
}
