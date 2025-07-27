// app/page.tsx
'use client'

import { useState } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import ExtractionViewer from './components/ExtractionViewer'

export default function HomePage() {
  const [fileId, setFileId] = useState<string | null>(null)
  const [extraction, setExtraction] = useState<any | null>(null)

  const handleFileUpload = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await axios.post('http://localhost:8000/upload_document/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (response.status === 200) {
      setFileId(response.data.file_id)
    }
  }

  const fetchExtraction = async () => {
    if (!fileId) return

    const response = await axios.get(`http://localhost:8000/get_extracted_text/${fileId}`)
    if (response.status === 200) {
      setExtraction(response.data)
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">🩺 Med-Assist</h1>
      <FileUpload onUpload={handleFileUpload} />

      {fileId && (
        <div className="mt-4">
          <button
            onClick={fetchExtraction}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Extract Text
          </button>
        </div>
      )}

      {extraction && <ExtractionViewer data={extraction} />}
    </main>
  )
}
