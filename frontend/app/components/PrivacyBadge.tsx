'use client'

import { useUnsecuredDeployment } from '../lib/deploymentContext'
import { Icon } from './Icon'

/**
 * The one claim the interface makes about how it works.
 *
 * It earns its place because it is about where the documents go, not about how
 * they were read: the analysis endpoint holds nothing after it answers, so
 * nothing the clinician submits outlives the request.
 *
 * On a deployment that is open to anyone, the badge is not shown at all. The
 * claim would still be true of the server - it stores nothing there either -
 * but "reste sur cette machine" is read as "reste sur la mienne", and on a
 * published address that reading is wrong and reassuring at the same time,
 * directly under a banner saying the opposite. A claim that has to be qualified
 * is not a badge; the warning says what matters instead.
 */
export function PrivacyBadge() {
  if (useUnsecuredDeployment()) return null

  return (
    <span className="flex items-center gap-2 rounded-full border border-accent-edge bg-accent-tint px-3.5 py-[7px] text-accent">
      <Icon name="shield" size={14} strokeWidth={1.8} />
      <span className="text-xs font-semibold">Reste sur cette machine</span>
    </span>
  )
}
