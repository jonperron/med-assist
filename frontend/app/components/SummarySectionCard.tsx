import type { SummarySection } from '../types/extraction'
import type { SelectedDocument } from '../lib/documentSelection'
import { sourceLabel } from '../lib/findingSource'

interface Props {
  section: SummarySection
  /** The batch this summary was built from, for naming a finding's source. */
  documents: SelectedDocument[]
  /** The anatomy section, folded in as a quiet line under the findings. */
  sites?: SummarySection | null
}

/**
 * One clinical axis of the summary.
 *
 * The findings are laid out one per line rather than as the section's ready-made
 * sentence: down a column a clinician scans them, and a sentence has to be read.
 * Both come from the same spans, so neither says more than the other.
 *
 * Each row carries the document it came from. Across a stack of documents that
 * is a clinical fact rather than a mechanism: a finding one letter mentions and
 * a finding three agree on are not read the same way.
 */
export function SummarySectionCard({ section, documents, sites = null }: Props) {
  return (
    <section
      data-print="section"
      aria-labelledby={`section-${section.key}`}
      className="flex flex-col gap-1 rounded-[10px] border border-rule bg-surface px-[30px] py-7"
    >
      <h2
        id={`section-${section.key}`}
        className="mb-3 font-serif text-[23px] font-normal text-ink"
      >
        {section.heading}
      </h2>

      <ul>
        {/* Keyed by position, not by the finding itself. The list is static
            within a render, and keying on content would tie this component to
            a backend dedup invariant that nothing here can enforce. */}
        {section.findings.map((finding, index) => {
          const source = sourceLabel(finding, documents)
          return (
            <li
              key={`${section.key}-${index}`}
              className="flex items-baseline justify-between gap-4 border-t border-rule-soft py-[11px]"
            >
              <span className="text-base text-ink">{finding.text}</span>
              {source && (
                <span className="shrink-0 text-right text-[12.5px] text-ink-muted">
                  {source}
                </span>
              )}
            </li>
          )
        })}
      </ul>

      {sites && sites.findings.length > 0 && (
        <p className="mt-2 border-t border-rule-soft pt-3.5 text-[13.5px] leading-[1.6] text-ink-muted">
          {sites.heading} : {sites.findings.map(finding => finding.text).join(', ')}
        </p>
      )}
    </section>
  )
}
