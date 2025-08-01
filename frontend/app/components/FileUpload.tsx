'use client'

import { useRef } from 'react'

interface Props {
  onUpload: (file: File) => void
}

export default function FileUpload({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
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
    </div>
  )
}
