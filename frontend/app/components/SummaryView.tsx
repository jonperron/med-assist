'use client'

import type { ClinicalSummary } from '../types/extraction'

interface Props {
  summary: ClinicalSummary
}

function documentCount(count: number): string {
  return count === 1 ? "d'après 1 document" : `d'après ${count} documents`
}

export default function SummaryView({ summary }: Props) {
  if (summary.empty) {
    return (
      <section className="mt-8" aria-labelledby="summary-heading">
        <h2 id="summary-heading" className="sr-only">
          Résumé
        </h2>
        <p role="status" className="text-gray-600">
          Aucun élément clinique n&apos;a été reconnu dans{' '}
          {summary.document_count === 1 ? 'ce document' : 'ces documents'}.
        </p>
      </section>
    )
  }

  return (
    <section className="mt-8" aria-labelledby="summary-heading">
      <h2 id="summary-heading" className="text-xl font-semibold text-gray-900">
        Résumé
      </h2>

      {summary.patient && (
        <p className="mt-2 text-lg text-gray-900">{summary.patient}</p>
      )}

      <dl className="mt-6 space-y-5">
        {summary.sections.map(section => (
          <div key={section.key}>
            <dt className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              {section.heading}
            </dt>
            <dd className="mt-1 text-gray-900 leading-relaxed">{section.sentence}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-6 text-sm text-gray-500">
        Résumé établi {documentCount(summary.document_count)}. À relire avant toute
        décision clinique.
      </p>
    </section>
  )
}
