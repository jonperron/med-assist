// app/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { AnalysisFailure } from './components/AnalysisFailure'
import { AppFooter } from './components/AppFooter'
import { AppHeader } from './components/AppHeader'
import { CautionNote } from './components/CautionNote'
import { DocumentList } from './components/DocumentList'
import { FileDropzone } from './components/FileDropzone'
import { PrivacyBadge } from './components/PrivacyBadge'
import { ReadingProgress } from './components/ReadingProgress'
import { SummaryView } from './components/SummaryView'
import {
  AnalysisStreamError,
  streamAnalysis,
  type StreamFailure,
} from './lib/analysisStream'
import { describeRejection, type SelectedDocument } from './lib/documentSelection'
import { documentFinished, startReading, type ReadingState } from './lib/readingState'
import type { AnalysisResponse } from './types/extraction'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const ANALYSIS_FAILED = "Échec de l'analyse des documents."

const CAVEAT =
  "Un résumé est un point de départ, pas un diagnostic. Relisez-le sur les documents eux-mêmes avant d'agir."

interface AnalysisFailureState {
  message: string
  reason: StreamFailure
}

let nextDocumentId = 0

function asSelected(files: File[]): SelectedDocument[] {
  return files.map(file => ({ id: `document-${(nextDocumentId += 1)}`, file }))
}

function actionLabel(count: number): string {
  return count === 1 ? 'Résumer ce document' : `Résumer ces ${count} documents`
}

function readFailure(error: unknown): AnalysisFailureState {
  if (error instanceof AnalysisStreamError) {
    return { message: error.message, reason: error.reason }
  }

  // A network error, or anything else fetch threw. The clinician's documents
  // are not implicated, so it must not read as though they were.
  return { message: ANALYSIS_FAILED, reason: 'transport' }
}

export default function HomePage() {
  const [documents, setDocuments] = useState<SelectedDocument[]>([])
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  // Two separate refusals. A file this interface will not accept is the
  // clinician's next move at the dropzone; an analysis that failed is a
  // report on the request they already made, and they must not read as one.
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [analysisError, setAnalysisError] = useState<AnalysisFailureState | null>(null)
  const [reading, setReading] = useState<ReadingState | null>(null)

  // The request in flight, so leaving the screen or starting another one stops
  // reading the stream rather than letting it settle over a batch that is no
  // longer on screen.
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => () => inFlight.current?.abort(), [])

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
    inFlight.current?.abort()
    setDocuments([])
    setAnalysis(null)
    setSelectionError(null)
    setAnalysisError(null)
    setReading(null)
  }

  const analyse = async (selected: SelectedDocument[]) => {
    if (selected.length === 0) return

    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    setAnalysisError(null)
    setAnalysis(null)
    setReading(startReading(selected.length))

    try {
      // A finished stream is not proof the body is ours: a stale base URL can
      // reach a proxy that streams something else entirely. `streamAnalysis`
      // is where that is decided - it refuses a result this screen could not
      // render and raises a `transport` failure instead, so there is one copy
      // of the rule rather than two that can drift.
      const received = await streamAnalysis(
        `${API_URL}/api/analyze/stream`,
        selected.map(({ file }) => file),
        {
          // The count the server accepted, which is what the later indices
          // are positions into.
          onBatch: total => setReading(startReading(total)),
          onDocument: (index, read) =>
            setReading(current =>
              current ? documentFinished(current, index, read) : current
            ),
        },
        ANALYSIS_FAILED,
        controller.signal
      )

      setAnalysis(received)
    } catch (error: unknown) {
      // An aborted request was replaced or abandoned on purpose. Reporting it
      // would put a failure on screen for something the clinician did.
      if (controller.signal.aborted) return
      setAnalysisError(readFailure(error))
    } finally {
      if (!controller.signal.aborted) setReading(null)
    }
  }

  if (analysis) {
    return (
      <SummaryView analysis={analysis} documents={documents} onStartOver={startOver} />
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

        {reading ? (
          <ReadingProgress
            documents={documents}
            states={reading.states}
            finished={reading.finished}
          />
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
                message={analysisError.message}
                reason={analysisError.reason}
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

      <AppFooter />
    </div>
  )
}
