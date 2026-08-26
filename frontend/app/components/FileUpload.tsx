'use client'

import { useRef, useState } from 'react'

interface Props {
  onUpload: (files: File[]) => void
  disabled?: boolean
}

const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'txt'])
const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
])

// Mirrors MAX_BATCH_FILES in the backend. Checked here too so a clinician who
// selects a folder is told before the upload rather than after it.
const MAX_FILES = 20

function isAccepted(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  return ALLOWED_EXTENSIONS.has(extension) && ALLOWED_MIME_TYPES.has(file.type)
}

export default function FileUpload({ onUpload, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return

    if (files.length > MAX_FILES) {
      setLocalError(`Trop de documents à la fois. Maximum : ${MAX_FILES}.`)
      e.target.value = ''
      return
    }

    // The whole selection is refused rather than filtered: silently dropping a
    // document would produce a summary missing a source nobody was told about.
    if (!files.every(isAccepted)) {
      setLocalError('Type de fichier invalide. Formats autorisés : PDF, DOCX, TXT.')
      e.target.value = ''
      return
    }

    setLocalError(null)
    onUpload(files)
    // Cleared so selecting the same documents again re-runs the analysis.
    e.target.value = ''
  }

  return (
    <div className="border border-gray-300 p-4 rounded-md">
      <label htmlFor="documents" className="block text-sm text-gray-700 mb-2">
        Documents à résumer (PDF, DOCX ou TXT)
      </label>
      <input
        id="documents"
        type="file"
        multiple
        ref={inputRef}
        accept=".pdf,.docx,.txt"
        disabled={disabled}
        onChange={handleFileChange}
        className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue-100 file:text-blue-700 hover:file:bg-blue-200 disabled:opacity-50"
      />
      <p className="mt-2 text-xs text-gray-500">
        Plusieurs documents d&apos;un même patient sont résumés ensemble.
      </p>
      {localError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {localError}
        </p>
      )}
    </div>
  )
}
