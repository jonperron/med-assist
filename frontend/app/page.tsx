// app/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { AnalysisFailure } from './components/AnalysisFailure'
import { AppHeader } from './components/AppHeader'
import { CautionNote } from './components/CautionNote'
import { DocumentList } from './components/DocumentList'
import { FileDropzone } from './components/FileDropzone'
import { PrivacyBadge } from './components/PrivacyBadge'
import { ReadingProgress } from './components/ReadingProgress'
import { ServiceUnavailableNotice } from './components/ServiceUnavailableNotice'
import { SummaryView } from './components/SummaryView'
import {
  AnalysisStreamError,
  streamAnalysis,
  type StreamFailure,
} from './lib/analysisStream'
import { apiBaseUrl } from './lib/contentSecurityPolicy'
import { describeRejection, type SelectedDocument } from './lib/documentSelection'
import { documentFinished, startReading, type ReadingState } from './lib/readingState'
import {
  canAnalyse,
  checkService,
  nextCheckDelay,
  type ServiceStatus,
} from './lib/serviceStatus'
import type { AnalysisResponse } from './types/extraction'

// Resolved by the same function the Content-Security-Policy is built from, so
// the origin this page calls is by construction the origin the policy allows.
const API_URL = apiBaseUrl(process.env.NEXT_PUBLIC_API_URL)

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
  // Whether the backend can analyse anything at all, kept current in the
  // background. It is not part of a batch: it survives every start-over and is
  // asked about before the clinician has selected a single document.
  const [service, setService] = useState<ServiceStatus>('unknown')

  // The request in flight, so leaving the screen or starting another one stops
  // reading the stream rather than letting it settle over a batch that is no
  // longer on screen.
  const inFlight = useRef<AbortController | null>(null)

  // Asks the readiness poll to check now rather than at its next tick. Held in
  // a ref because the poll owns the timer and the abort controller, and an
  // analysis that just failed is evidence worth acting on immediately.
  const recheck = useRef<() => void>(() => {})

  useEffect(() => () => inFlight.current?.abort(), [])

  // Polled rather than checked once, because the state this reports is one the
  // clinician is waiting out: a cold backend is ready seconds later, and the
  // banner clearing by itself is what saves them reloading the page. Each check
  // schedules the next, so a slow answer cannot stack requests the way a bare
  // setInterval would - `checkService` carries its own deadline so a request
  // that never settles cannot stop the loop.
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let checking = false

    const check = async () => {
      // A check asked for out of band while one is already running would put
      // two in flight and leave the later answer to be overwritten by the
      // earlier one.
      if (checking) return
      checking = true
      // Whatever was scheduled is superseded by this run.
      if (timer) clearTimeout(timer)

      try {
        const status = await checkService(API_URL, controller.signal)
        // Unmounted while the answer was in flight. `checkService` reports an
        // abort as a non-answer like any other, and setting that here would be
        // a warning about a screen that is gone.
        if (controller.signal.aborted) return

        setService(status)
        timer = setTimeout(check, nextCheckDelay(status))
      } finally {
        checking = false
      }
    }

    recheck.current = () => void check()
    void check()

    // A hidden tab has its timers throttled to roughly a minute, so a clinician
    // who switched away during a cold start would come back to a stale warning
    // for a service that is long since up. The notice promises the screen
    // updates by itself; this is what keeps that true on return.
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      controller.abort()
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
      recheck.current = () => {}
    }
  }, [])

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

      const failure = readFailure(error)
      setAnalysisError(failure)

      // The request just carried back an answer about the service itself, which
      // is better evidence than the next scheduled poll and up to 30 seconds
      // earlier. A batch that could not be read says nothing about the service,
      // so it is not a reason to go and ask.
      if (failure.reason === 'server_error' || failure.reason === 'transport') {
        recheck.current()
      }
    } finally {
      if (!controller.signal.aborted) setReading(null)
    }
  }

  // `unknown` is the first round trip and shows nothing: a warning rendered
  // while the very first check is still open would flash on every load of a
  // healthy deployment. `canAnalyse` is deliberately narrower than the notice -
  // only the service's own refusal takes the submit button away, so a probe
  // that merely could not be reached cannot disable a working deployment.
  const down = service === 'unavailable' || service === 'unreachable'
  const analysable = canAnalyse(service)

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
            {down && <ServiceUnavailableNotice reason={service} />}

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
                canRetry={analysable}
                onRetry={() => analyse(documents)}
                onStartOver={startOver}
              />
            )}

            {documents.length > 0 && (
              <div className="flex flex-wrap items-center gap-[18px]">
                {/*
                 * Held shut while the service cannot answer, rather than left
                 * to send a batch that comes back 503. The notice above says
                 * why, and the poll reopens it without a reload.
                 */}
                <button
                  type="button"
                  onClick={() => analyse(documents)}
                  disabled={!analysable}
                  className="h-13 cursor-pointer rounded-lg border border-accent bg-accent px-7 text-[15.5px] font-semibold text-surface hover:bg-accent-strong disabled:cursor-not-allowed disabled:border-rule disabled:bg-rule-soft disabled:text-ink-muted"
                >
                  {actionLabel(documents.length)}
                </button>
                {analysable && (
                  <span className="text-[13.5px] text-ink-muted">
                    Environ une demi-minute.
                  </span>
                )}
              </div>
            )}
          </>
        )}

        <CautionNote>{CAVEAT}</CautionNote>
      </main>
    </div>
  )
}
