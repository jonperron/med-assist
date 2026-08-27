import { Icon } from './Icon'

/**
 * The one claim the interface makes about how it works.
 *
 * It earns its place because it is about where the documents go, not about how
 * they were read: the analysis endpoint holds nothing after it answers, so
 * nothing the clinician submits outlives the request.
 */
export function PrivacyBadge() {
  return (
    <span className="flex items-center gap-2 rounded-full border border-accent-edge bg-accent-tint px-3.5 py-[7px] text-accent">
      <Icon name="shield" size={14} strokeWidth={1.8} />
      <span className="text-xs font-semibold">Reste sur cette machine</span>
    </span>
  )
}
