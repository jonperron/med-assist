import { APP_VERSION, ISSUES_URL } from '../lib/version'

/**
 * The standing line under every screen: what happened to the documents, which
 * build read them, and where to say it went wrong.
 *
 * The privacy sentence is the badge's claim spelled out. The badge says where
 * the documents go; this says what is left afterwards, which is the question a
 * clinician asks second and the one a footer is the right size for. It is set
 * in `ink-soft` rather than the `ink-muted` this size of chrome would normally
 * take: at 3.6:1 on white, muted is below the contrast floor, and of all the
 * text on screen this is the sentence that must not be the hard one to read.
 *
 * Full-bleed with the same `px-10` as `AppHeader`, so the two pieces of chrome
 * line up with each other. They cannot also line up with `main`, whose column
 * is 760px on one screen and 1160px on the other.
 *
 * Hidden in print. A summary going into a patient file is about the patient,
 * and a version number and an issue tracker are about this software.
 */
export function AppFooter() {
  return (
    <footer
      data-print="hide"
      className="flex flex-wrap items-baseline justify-between gap-x-10 gap-y-3 border-t border-rule bg-surface px-10 py-5"
    >
      <p className="max-w-[620px] text-[13px] leading-[1.55] text-pretty text-ink-soft">
        Aucun document n&apos;est enregistré sur le serveur. Les fichiers ne vivent que
        le temps de la requête, dans un stockage temporaire effacé avec la réponse :
        pas de base de données, rien à supprimer ensuite.
      </p>
      <div className="flex items-baseline gap-5 text-[13px] text-ink-soft">
        <span>
          Med-Assist{' '}
          {/* Tabular figures so the number does not shift the link beside it
              when a build changes its width. */}
          <span className="tabular-nums">v{APP_VERSION}</span>
        </span>
        <a
          href={ISSUES_URL}
          target="_blank"
          // `noreferrer` as well as `noopener`: `Referrer-Policy: no-referrer`
          // already covers this, but the header is set in `next.config.ts` and
          // the link should not depend on it staying there.
          rel="noopener noreferrer"
          // The tab change announced rather than sprung: part of the accessible
          // name, so a screen reader reaches it with the label instead of after
          // the click. Stated here rather than in a visually-hidden span
          // because the name algorithm trims each text node, so a span holding
          // a leading space yields "problème(nouvel onglet)". The visible text
          // stays a prefix of the label, which is what voice control needs.
          aria-label="Signaler un problème (nouvel onglet)"
          className="font-medium text-accent underline decoration-accent-edge underline-offset-[3px] hover:decoration-accent"
        >
          Signaler un problème
        </a>
      </div>
    </footer>
  )
}
