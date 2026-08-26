'use client'

import type { ClinicalSummary } from '../types/extraction'
import type { SelectedDocument } from '../lib/documentSelection'
import { layoutSummary, SITES_HOST_KEY } from '../lib/summaryLayout'
import { AppHeader } from './AppHeader'
import { CautionNote } from './CautionNote'
import { EmptySummary } from './EmptySummary'
import { Icon } from './Icon'
import { PrivacyBadge } from './PrivacyBadge'
import { SourceChips } from './SourceChips'
import { SummarySectionCard } from './SummarySectionCard'

interface Props {
  summary: ClinicalSummary
  documents: SelectedDocument[]
  onStartOver: () => void
}

const CAVEAT =
  "Ce résumé rapporte ce que disent les documents. Il laisse de côté ce que la lecture n'a pas reconnu : relisez-le sur les documents eux-mêmes avant d'agir."

function summaryTitle(count: number): string {
  return count === 1 ? "Résumé d'un document" : `Résumé de ${count} documents`
}

export default function SummaryView({ summary, documents, onStartOver }: Props) {
  const { cards, sites } = layoutSummary(summary.sections)

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
            {summary.patient && (
              <span className="text-[14.5px] text-ink-muted">{summary.patient}</span>
            )}
          </div>
          {/* Where a retention clock would sit if there were anything to
              count down: this path stores nothing, so it says so instead. */}
          <div data-print="hide">
            <PrivacyBadge />
          </div>
        </div>

        <div data-print="hide">
          <SourceChips documents={documents} />
        </div>

        {summary.empty ? (
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
