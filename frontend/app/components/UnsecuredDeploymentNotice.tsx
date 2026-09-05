import { Icon } from './Icon'

/**
 * The banner a publicly reachable deployment shows on every screen.
 *
 * Med-Assist is a research project whose product is the NER model. The API it
 * is served behind authenticates nobody: anyone who can reach the address can
 * submit documents, and nothing about the connection between this page and that
 * service is private to the person using it. Locally that is fine and this
 * banner is off. Published at a public address it is the single most important
 * thing on the screen, because the person about to use it is a clinician and
 * the documents they are about to drop are somebody's medical history.
 *
 * So the copy says the one thing that changes what they do: do not put a real
 * patient's documents here. It does not describe the deployment, name what is
 * missing, or offer a workaround - an operator reads `deploy/README.md` for
 * that, and a clinician needs a sentence, not a threat model.
 *
 * It sits above the header rather than inside the page body so that it is
 * present on the summary screen too. A warning that disappears once the
 * analysis starts would be a warning shown only while it is not yet needed.
 */
export function UnsecuredDeploymentNotice() {
  return (
    <div
      // Assertive rather than polite: it is not the state of the machine, it is
      // a thing to know before touching anything, and it is on screen from the
      // first paint rather than arriving later.
      role="alert"
      // Named, like the status regions on these screens: `AnalysisFailure` is
      // also an unnamed `alert`, and two same-role regions with nothing to tell
      // them apart are indistinguishable to a screen reader and unselectable in
      // a test. The role is kept even though it is present at first paint,
      // where assistive tech may not announce it - the text is read in document
      // order regardless, and it sits above everything else on the page.
      aria-label="Avertissement sur cette installation"
      className="flex items-start gap-3 border-b border-failure-edge bg-failure-tint px-6 py-3.5"
    >
      <Icon
        name="warning"
        size={18}
        strokeWidth={1.8}
        className="mt-px shrink-0 text-failure"
      />
      <p className="text-[13.5px] leading-[1.55] text-pretty text-ink-soft">
        <span className="font-semibold text-ink">
          Démonstration publique — n&apos;y déposez aucun document réel.
        </span>{' '}
        Cette installation sert à faire la démonstration d&apos;un travail de
        recherche. Elle est ouverte : n&apos;importe qui peut y accéder, et les
        documents envoyés peuvent être lus par un tiers. Utilisez des documents
        fictifs.
      </p>
    </div>
  )
}
