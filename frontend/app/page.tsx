// app/page.tsx
'use client'

import { useState } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import ExtractionViewer from './components/ExtractionViewer'

interface EntityDetail {
  text: string
  label: string
  score: number
  start: number
  end: number
}

interface ExtractedEntities {
  patient_info: EntityDetail[]
  anatomy: EntityDetail[]
  symptoms: EntityDetail[]
  examinations: EntityDetail[]
  treatments: EntityDetail[]
  pathologies: EntityDetail[]
  temporal: EntityDetail[]
  measurements: EntityDetail[]
  other: EntityDetail[]
}

interface ExtractionData {
  file_id: string
  text: string
  extracted_entities: ExtractedEntities
  processed_at?: string | null
  mapping_info?: {
    language: string
    dataset: string
    description: string
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

export default function HomePage() {
  const [fileId, setFileId] = useState<string | null>(null)
  const [extraction, setExtraction] = useState<ExtractionData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileUpload = async (file: File) => {
    try {
      setError(null)
      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(`${API_URL}/api/upload_document/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      if (response.status === 200) {
        setFileId(response.data.file_id)
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Failed to upload file')
      console.error('Upload error:', err)
    }
  }

  const fetchExtraction = async () => {
    if (!fileId) return

    try {
      setError(null)
      const response = await axios.get(`${API_URL}/api/get_extracted_text/${fileId}`)
      if (response.status === 200) {
        setExtraction(response.data)
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Failed to fetch extraction')
      console.error('Extraction error:', err)
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">🩺 Med-Assist</h1>
      <p className="text-sm text-gray-500 mb-4">API: {API_URL}</p>
      <FileUpload onUpload={handleFileUpload} />

      {error && (
        <div className="mt-4 p-3 bg-red-100 text-red-700 rounded">
          {error}
        </div>
      )}

      {fileId && (
        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">File ID: {fileId}</p>
          <button
            onClick={fetchExtraction}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Extract Text
          </button>
        </div>
      )}

      {extraction && extraction.text && <ExtractionViewer data={extraction} />}
    </main>
  )
}
