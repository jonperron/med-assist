// app/page.tsx
'use client'

import { useState } from 'react'
import axios from 'axios'
import { AnalysisFailure } from './components/AnalysisFailure'
import { AppHeader } from './components/AppHeader'
import { CautionNote } from './components/CautionNote'
import { DocumentList } from './components/DocumentList'
import { FileDropzone } from './components/FileDropzone'
import { PrivacyBadge } from './components/PrivacyBadge'
import { ReadingProgress } from './components/ReadingProgress'
import { SummaryView } from './components/SummaryView'
import { errorMessage } from './lib/apiError'
import { describeRejection, type SelectedDocument } from './lib/documentSelection'
import type { AnalysisResponse, ClinicalSummary } from './types/extraction'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const ANALYSIS_FAILED = "Échec de l'analyse des documents."

const CAVEAT =
  "Un résumé est un point de départ, pas un diagnostic. Relisez-le sur les documents eux-mêmes avant d'agir."

let nextDocumentId = 0

function asSelected(files: File[]): SelectedDocument[] {
  return files.map(file => ({ id: `document-${(nextDocumentId += 1)}`, file }))
}

function actionLabel(count: number): string {
  return count === 1 ? 'Résumer ce document' : `Résumer ces ${count} documents`
}

export default function HomePage() {
  const [documents, setDocuments] = useState<SelectedDocument[]>([])
  const [summary, setSummary] = useState<ClinicalSummary | null>(null)
  // Two separate refusals. A file this interface will not accept is the
  // clinician's next move at the dropzone; an analysis that failed is a
  // report on the request they already made, and they must not read as one.
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const addDocuments = (files: File[]) => {
    const rejection = describeRejection(files, documents.length)
    if (rejection) {
      setSelectionError(rejection)
      return
    }

    // Minted here, not inside the updater: `asSelected` advances a
    // module-level counter, and React may call an updater more than once.
    const added = asSelected(files)

    setSelectionError(null)
    setAnalysisError(null)
    setDocuments(current => [...current, ...added])
  }

  const removeDocument = (id: string) => {
    // The failure card describes a request made against a particular batch.
    // Once the batch changes it no longer describes anything, and its retry
    // would re-send something the clinician did not ask for.
    setAnalysisError(null)
    setDocuments(current => current.filter(document => document.id !== id))
  }

  const removeAllDocuments = () => {
    setAnalysisError(null)
    setSelectionError(null)
    setDocuments([])
  }

  const startOver = () => {
    setDocuments([])
    setSummary(null)
    setSelectionError(null)
    setAnalysisError(null)
  }

  const analyse = async (selected: SelectedDocument[]) => {
    if (selected.length === 0) return

    const formData = new FormData()
    // One field name repeated per file: what FastAPI reads as List[UploadFile].
    selected.forEach(({ file }) => formData.append('files', file))

    try {
      setAnalysisError(null)
      setPending(true)
      setSummary(null)

      const response = await axios.post<AnalysisResponse>(
        `${API_URL}/api/analyze`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )

      // A 200 is not proof the body is ours: a stale base URL can reach a
      // proxy or a login page. Storing a missing summary would end the
      // spinner and return the clinician to the picker saying nothing.
      const received = response.data?.summary
      if (!received || !Array.isArray(received.sections)) {
        setAnalysisError(ANALYSIS_FAILED)
        return
      }

      setSummary(received)
    } catch (err: unknown) {
      setAnalysisError(errorMessage(err, ANALYSIS_FAILED))
    } finally {
      setPending(false)
    }
  }

  if (summary) {
    return (
      <SummaryView summary={summary} documents={documents} onStartOver={startOver} />
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <AppHeader>
        <PrivacyBadge />
      </AppHeader>

      <main className="mx-auto flex w-full max-w-[760px] grow flex-col gap-8 px-6 py-13">
        <div className="flex flex-col gap-3.5">
          <h1 className="font-serif text-[38px] leading-[1.15] font-normal tracking-[-0.015em] text-ink">
            Résumer les documents d&apos;un patient
          </h1>
          <p className="max-w-[580px] text-[15.5px] leading-[1.6] text-pretty text-ink-soft">
            Ajoutez autant de documents que vous en avez. Med-Assist les lit ensemble et
            vous rend un seul résumé : les pathologies, les symptômes, les examens et les
            traitements qu&apos;ils contiennent.
          </p>
        </div>

        {pending ? (
          <ReadingProgress documents={documents} />
        ) : (
          <>
            <FileDropzone onAdd={addDocuments} />

            {selectionError && (
              <p role="alert" className="text-sm font-medium text-failure">
                {selectionError}
              </p>
            )}

            <DocumentList
              documents={documents}
              onRemove={removeDocument}
              onRemoveAll={removeAllDocuments}
            />

            {analysisError && documents.length > 0 && (
              <AnalysisFailure
                message={analysisError}
                onRetry={() => analyse(documents)}
                onStartOver={startOver}
              />
            )}

            {documents.length > 0 && (
              <div className="flex flex-wrap items-center gap-[18px]">
                <button
                  type="button"
                  onClick={() => analyse(documents)}
                  className="h-13 cursor-pointer rounded-lg border border-accent bg-accent px-7 text-[15.5px] font-semibold text-surface hover:bg-accent-strong"
                >
                  {actionLabel(documents.length)}
                </button>
                <span className="text-[13.5px] text-ink-muted">
                  Environ une demi-minute.
                </span>
              </div>
            )}
          </>
        )}

        <CautionNote>{CAVEAT}</CautionNote>
      </main>
    </div>
  )
}
