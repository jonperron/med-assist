'use client'

/**
 * The last resort, when a render throws.
 *
 * Without it a throw lands on Next's built-in boundary, which in development
 * surfaces the offending value in an overlay - and on these screens the
 * offending value is patient-derived. This renders a content-free card
 * instead. It deliberately shows nothing about the error: not the message,
 * not the digest, not a stack.
 *
 * Nothing reaches a logging sink here either. The clinician's way out is to
 * start again, which discards the page state the failure came from.
 */
export default function AnalysisBoundary({ reset }: { reset: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div
        role="alert"
        className="flex max-w-[520px] flex-col gap-3 rounded-[10px] border border-failure-edge bg-surface px-7 py-6"
      >
        <span className="text-[15.5px] font-semibold text-ink">
          L&apos;affichage du résumé a échoué
        </span>
        <span className="text-sm leading-[1.6] text-pretty text-ink-soft">
          Rien n&apos;a été conservé. Reprenez depuis vos documents.
        </span>
        <button
          type="button"
          onClick={reset}
          className="mt-1 h-11 w-fit cursor-pointer rounded-lg border border-accent bg-accent px-5 text-sm font-semibold text-surface hover:bg-accent-strong"
        >
          Recommencer
        </button>
      </div>
    </div>
  )
}
