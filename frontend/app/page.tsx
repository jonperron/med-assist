// app/page.tsx
'use client'

import { useState } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import SummaryView from './components/SummaryView'
import type { AnalysisResponse, ClinicalSummary } from './types/extraction'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// The API answers errors as {"detail": {"message": ...}}; older shapes and
// network failures fall back to the caller's wording.
function errorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback
  const data = err.response?.data
  return data?.detail?.message || data?.message || fallback
}

export default function HomePage() {
  const [summary, setSummary] = useState<ClinicalSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const handleUpload = async (files: File[]) => {
    const formData = new FormData()
    // One field name repeated per file: what FastAPI reads as List[UploadFile].
    files.forEach(file => formData.append('files', file))

    try {
      setError(null)
      setPending(true)
      setSummary(null)

      const response = await axios.post<AnalysisResponse>(
        `${API_URL}/api/analyze`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )

      setSummary(response.data.summary)
    } catch (err: unknown) {
      setError(errorMessage(err, "Échec de l'analyse des documents."))
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">Med-Assist</h1>

      <FileUpload onUpload={handleUpload} disabled={pending} />

      {pending && (
        <p role="status" className="mt-4 text-gray-600">
          Analyse en cours…
        </p>
      )}

      {error && (
        <div role="alert" className="mt-4 p-3 bg-red-100 text-red-700 rounded">
          {error}
        </div>
      )}

      {summary && <SummaryView summary={summary} />}
    </main>
  )
}
