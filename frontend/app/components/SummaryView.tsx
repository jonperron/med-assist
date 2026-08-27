'use client'

import type { AnalysisResponse } from '../types/extraction'
import type { SelectedDocument } from '../lib/documentSelection'
import { formatDateRange } from '../lib/documentDate'
import { safeText } from '../lib/safeText'
import { layoutSummary, SITES_HOST_KEY } from '../lib/summaryLayout'
import { unreadDocuments } from '../lib/unreadDocuments'
import { AppHeader } from './AppHeader'
import { CautionNote } from './CautionNote'
import { EmptySummary } from './EmptySummary'
import { Icon } from './Icon'
import { PrivacyBadge } from './PrivacyBadge'
import { SourceChips } from './SourceChips'
import { SummarySectionCard } from './SummarySectionCard'
import { UnreadNotice } from './UnreadNotice'

interface Props {
  /** The whole answer: the summary, and each document as the API read it. */
  analysis: AnalysisResponse
  documents: SelectedDocument[]
  onStartOver: () => void
}

const CAVEAT =
  "Ce résumé rapporte ce que disent les documents. Il laisse de côté ce que la lecture n'a pas reconnu : relisez-le sur les documents eux-mêmes avant d'agir."

function summaryTitle(count: number): string {
  return count === 1 ? "Résumé d'un document" : `Résumé de ${count} documents`
}

export function SummaryView({ analysis, documents, onStartOver }: Props) {
  const { summary } = analysis
  const { cards, sites } = layoutSummary(summary.sections)
  const span = formatDateRange(summary.date_range)
  const unread = unreadDocuments(analysis.documents, documents)

  // Derived from the content, with `empty` as a hint rather than the decision.
  // The backend sets `empty` only when there is no patient line either, so a
  // batch whose sole finding was an age arrives as `empty: false` with no
  // sections - and branching on the flag alone renders an empty grid.
  const nothingToShow = summary.empty || cards.length === 0

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <AppHeader>
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => window.print()}
            className="flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-edge bg-surface px-4 text-sm font-semibold text-ink hover:bg-paper"
          >
            <Icon name="printer" size={16} />
            Imprimer
          </button>
          <button
            type="button"
            onClick={onStartOver}
            className="h-10 cursor-pointer rounded-lg border border-transparent px-4 text-sm font-semibold text-ink-soft hover:text-ink"
          >
            Nouveau résumé
          </button>
        </div>
      </AppHeader>

      <main className="mx-auto flex w-full max-w-[1160px] grow flex-col gap-[30px] px-10 py-11">
        <div className="flex flex-wrap items-end justify-between gap-8">
          <div className="flex flex-col gap-2">
            <h1 className="font-serif text-[34px] leading-[1.15] font-normal tracking-[-0.015em] text-ink">
              {summaryTitle(summary.document_count)}
            </h1>
            {/* The span the documents cover, where a clinician places what
                they are about to read. Absent when nothing could be dated,
                which is common and is not a fault. */}
            {span && <span className="text-[14.5px] text-ink-soft">{span}</span>}
            {/* The demographic line is built from spans the model marked, so
                it is document text like the findings are. */}
            {summary.patient && (
              <span className="text-[14.5px] text-ink-muted">
                {safeText(summary.patient)}
              </span>
            )}
          </div>
          {/* Where a retention clock would sit if there were anything to
              count down: this path stores nothing, so it says so instead. */}
          <div data-print="hide">
            <PrivacyBadge />
          </div>
        </div>

        {/* Above the chips, not below: what the summary is missing has to be
            read before the summary, not after it. */}
        <UnreadNotice documents={unread} />

        {/* Kept in the printed copy on purpose: on a page going into a
            patient file, which documents the summary was built from is the
            first thing a reader needs to check it against. */}
        <SourceChips documents={documents} analyzed={analysis.documents} />

        {nothingToShow ? (
          <EmptySummary
            documentCount={summary.document_count}
            onStartOver={onStartOver}
          />
        ) : (
          <div className="grid grid-cols-1 items-start gap-10 md:grid-cols-2">
            {cards.map(section => (
              <SummarySectionCard
                key={section.key}
                section={section}
                documents={documents}
                sites={section.key === SITES_HOST_KEY ? sites : null}
              />
            ))}
          </div>
        )}

        <CautionNote>{CAVEAT}</CautionNote>
      </main>
    </div>
  )
}
