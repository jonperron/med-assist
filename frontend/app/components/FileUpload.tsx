'use client'

import { useRef, useState } from 'react'

interface Props {
  onUpload: (file: File) => void
}

const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'txt'])
const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
])

export default function FileUpload({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
      const hasValidExtension = ALLOWED_EXTENSIONS.has(extension)
      const hasValidMimeType = ALLOWED_MIME_TYPES.has(file.type)

      if (!hasValidExtension || !hasValidMimeType) {
        setLocalError('Type de fichier invalide. Formats autorises: PDF, DOCX, TXT.')
        e.target.value = ''
        return
      }

      setLocalError(null)
      onUpload(file)
    }
  }

  return (
    <div className="border border-gray-300 p-4 rounded-md">
      <input
        type="file"
        ref={inputRef}
        accept=".pdf,.docx,.txt"
        onChange={handleFileChange}
        className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-blue-100 file:text-blue-700 hover:file:bg-blue-200"
      />
      {localError && <p className="mt-2 text-sm text-red-600">{localError}</p>}
    </div>
  )
}
