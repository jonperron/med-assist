import { Icon } from './Icon'

interface Props {
  /**
   * Which of the two failing states this is. They are different situations for
   * the clinician: one is a wait, the other is someone else's problem.
   */
  reason: 'unavailable' | 'unreachable'
}

const COPY: Record<Props['reason'], { headline: string; detail: string }> = {
  // The service answered and said it cannot analyse - a cold start, almost
  // always. The wait is seconds, and the screen clears itself.
  unavailable: {
    headline: "Le service n'est pas disponible",
    detail:
      'Aucun document ne peut être analysé pour le moment. Si Med-Assist vient de ' +
      'démarrer, patientez quelques instants : cet écran se met à jour tout seul, ' +
      'inutile de le recharger. Si le message reste, prévenez la personne qui ' +
      "administre l'installation.",
  },
  // Nothing answered at all. The analysis may well work, so this reports
  // without promising either way - and the button stays available.
  unreachable: {
    headline: 'Med-Assist ne répond pas',
    detail:
      "L'application n'arrive pas à joindre le service. Vous pouvez tout de même " +
      'lancer un résumé, mais il risque de ne pas aboutir. Si le message reste, ' +
      "prévenez la personne qui administre l'installation.",
  },
}

/**
 * The service cannot analyse anything, or cannot be reached to find out.
 *
 * Shown before the clinician commits to anything, because the alternative is
 * that they gather documents, submit them and read a refusal - which looks like
 * their scans were rejected. This says the service is down before they start.
 *
 * It takes the failure palette rather than the ochre one: the caveat bar at the
 * bottom of the screen is already ochre, and two of those read as one notice
 * split in half. It is also not a caution - nothing here is a thing to be
 * careful about, it is a thing that does not work.
 *
 * What it does not say is why. The backend answers readiness with a fixed
 * string carrying no path and no configuration, and the interface names no
 * model, no version and no timing anywhere else either.
 */
export function ServiceUnavailableNotice({ reason }: Props) {
  const { headline, detail } = COPY[reason]

  return (
    <div
      // Polite, not assertive: this is the state of the machine on arrival
      // rather than the result of something the clinician just did.
      role="status"
      // Named because three other components on these screens are also
      // `role="status"`. Without a name a screen reader announces two polite
      // regions with nothing to tell them apart, and a test cannot select one.
      aria-label="État du service"
      className="flex items-start gap-3.5 rounded-[10px] border border-failure-edge bg-surface px-5 py-[18px]"
    >
      <Icon
        name="warning"
        size={20}
        strokeWidth={1.7}
        className="mt-0.5 shrink-0 text-failure"
      />
      <div className="flex flex-col gap-[7px]">
        <span className="text-[15.5px] font-semibold text-ink">{headline}</span>
        <span className="text-sm leading-[1.6] text-pretty text-ink-soft">{detail}</span>
      </div>
    </div>
  )
}
