import type { SummarySection } from '../types/extraction'

interface Props {
  section: SummarySection
  /** The anatomy section, folded in as a quiet line under the findings. */
  sites?: SummarySection | null
}

/**
 * One clinical axis of the summary.
 *
 * The findings are laid out one per line rather than as the section's ready-made
 * sentence: down a column a clinician scans them, and a sentence has to be read.
 * Both come from the same spans, so neither says more than the other.
 */
export function SummarySectionCard({ section, sites = null }: Props) {
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
        {section.findings.map((finding, index) => (
          <li
            key={`${section.key}-${index}`}
            className="border-t border-rule-soft py-[11px] text-base text-ink"
          >
            {finding}
          </li>
        ))}
      </ul>

      {sites && sites.findings.length > 0 && (
        <p className="mt-2 border-t border-rule-soft pt-3.5 text-[13.5px] leading-[1.6] text-ink-muted">
          {sites.heading} : {sites.findings.join(', ')}
        </p>
      )}
    </section>
  )
}
