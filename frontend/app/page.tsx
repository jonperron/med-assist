// app/page.tsx
'use client'

import { useState } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import ExtractionViewer from './components/ExtractionViewer'
import RetentionNotice from './components/RetentionNotice'

interface EntityDetail {
  text: string
  label: string
  score: number
  start?: number | null
  end?: number | null
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
  file_id?: string
  text?: string | null
  extracted_entities: ExtractedEntities
  processed_at?: string | null
  mapping_info?: {
    language: string
    dataset: string
    description: string
  }
  expires_in_seconds?: number | null
  retained?: boolean
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// The API answers errors as {"detail": {"message": ...}}; older shapes and
// network failures fall back to the caller's wording.
function errorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback
  const data = err.response?.data
  return data?.detail?.message || data?.message || fallback
}

export default function HomePage() {
  const [fileId, setFileId] = useState<string | null>(null)
  const [extraction, setExtraction] = useState<ExtractionData | null>(null)
  const [expiresIn, setExpiresIn] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [storeOnServer, setStoreOnServer] = useState(false)
  const [pseudonymize, setPseudonymize] = useState(false)

  const analyzeWithoutStoring = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('pseudonymize', String(pseudonymize))

    const response = await axios.post(`${API_URL}/api/analyze`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (response.status === 200) {
      setFileId(null)
      setExpiresIn(null)
      setExtraction(response.data)
    }
  }

  const uploadForLater = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('pseudonymize', String(pseudonymize))

    const response = await axios.post(`${API_URL}/api/upload_document/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (response.status === 200) {
      setFileId(response.data.file_id)
      setExpiresIn(response.data.expires_in_seconds ?? null)
      setExtraction(null)
    }
  }

  const handleFileUpload = async (file: File) => {
    try {
      setError(null)
      // The stateless path is the default: nothing about the document reaches
      // the server's storage, so there is nothing to expire or delete.
      await (storeOnServer ? uploadForLater(file) : analyzeWithoutStoring(file))
    } catch (err: unknown) {
      setError(errorMessage(err, 'Failed to analyze file'))
    }
  }

  const deleteDocument = async () => {
    if (!fileId) return

    try {
      setError(null)
      await axios.delete(`${API_URL}/api/documents/${fileId}`)
      setFileId(null)
      setExtraction(null)
      setExpiresIn(null)
    } catch (err: unknown) {
      setError(errorMessage(err, 'Failed to delete document'))
    }
  }

  const fetchExtraction = async () => {
    if (!fileId) return

    try {
      setError(null)
      const response = await axios.get(`${API_URL}/api/get_extracted_text/${fileId}`)
      if (response.status === 200) {
        setExtraction(response.data)
        setExpiresIn(response.data.expires_in_seconds ?? null)
      }
    } catch (err: unknown) {
      setError(errorMessage(err, 'Failed to fetch extraction'))
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">🩺 Med-Assist</h1>
      <FileUpload onUpload={handleFileUpload} />

      <div className="mt-3 space-y-2 text-sm text-gray-700">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={storeOnServer}
            onChange={e => setStoreOnServer(e.target.checked)}
          />
          Keep the document on the server so it can be reopened later
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={pseudonymize}
            onChange={e => setPseudonymize(e.target.checked)}
          />
          Mask detected patient identifiers
        </label>
        {!storeOnServer && (
          <p className="text-gray-500">
            Nothing is stored: the document is analyzed in one request and the result is
            only in this page.
          </p>
        )}
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-100 text-red-700 rounded">
          {error}
        </div>
      )}

      {fileId && (
        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">File ID: {fileId}</p>
          <div className="flex gap-2">
            <button
              onClick={fetchExtraction}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Extract Text
            </button>
            <button
              onClick={deleteDocument}
              className="px-4 py-2 border border-gray-400 text-gray-700 rounded hover:bg-gray-100"
            >
              Delete Now
            </button>
          </div>
          {expiresIn !== null && (
            // Keyed so a freshly reported expiry restarts the countdown at once.
            <RetentionNotice key={`${fileId}-${expiresIn}`} expiresInSeconds={expiresIn} />
          )}
        </div>
      )}

      {extraction && <ExtractionViewer data={extraction} />}
    </main>
  )
}
