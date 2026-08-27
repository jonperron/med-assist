import type { StreamFailure } from '../lib/analysisStream'
import { Icon } from './Icon'

interface Props {
  message: string
  /** Which kind of failure this is, for the headline above the message. */
  reason: StreamFailure
  onRetry: () => void
  onStartOver: () => void
}

// The three failures are three different things to tell a clinician: their
// documents did not work, the service did not work, or the answer never
// arrived. Only the first is worth trying another scan for.
const HEADLINES: Record<StreamFailure, string> = {
  unreadable_batch: "Aucun résumé n'a pu être établi",
  server_error: "L'analyse n'a pas abouti",
  transport: "L'analyse s'est interrompue",
}

/**
 * The headline for a reason, or the neutral one for a reason added later.
 *
 * `FailureReason` is closed today and `UnreadableReason` beside it is
 * documented as meant to grow, so a member arriving that this build predates
 * is a question of when. An alert whose first line is empty tells a clinician
 * less than the generic wording does.
 */
function headlineFor(reason: StreamFailure): string {
  return Object.hasOwn(HEADLINES, reason) ? HEADLINES[reason] : HEADLINES.transport
}

/**
 * The refusal, shown whole.
 *
 * The backend deliberately does not name the file behind a refused batch, so
 * this card cannot either. What it can do is branch on `reason` rather than on
 * the wording: `POST /api/analyze/stream` sends a closed reason code beside
 * its message precisely so a client does not have to read English prose to
 * tell a bad document from a failed service.
 */
export function AnalysisFailure({ message, reason, onRetry, onStartOver }: Props) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3.5 rounded-[10px] border border-failure-edge bg-surface px-5 py-[18px]"
    >
      <Icon
        name="warning"
        size={20}
        strokeWidth={1.7}
        className="mt-0.5 shrink-0 text-failure"
      />
      <div className="flex grow flex-col gap-[7px]">
        <span className="text-[15.5px] font-semibold text-ink">
          {headlineFor(reason)}
        </span>
        <span className="text-sm leading-[1.6] text-pretty text-ink-soft">{message}</span>
        <div className="flex flex-wrap items-center gap-2.5 pt-1.5">
          <button
            type="button"
            onClick={onRetry}
            className="h-11 cursor-pointer rounded-lg border border-edge bg-surface px-5 text-sm font-semibold text-ink hover:bg-paper"
          >
            Réessayer
          </button>
          <button
            type="button"
            onClick={onStartOver}
            className="h-11 cursor-pointer rounded-lg border border-transparent px-5 text-sm font-semibold text-ink-soft hover:text-ink"
          >
            Choisir d&apos;autres documents
          </button>
        </div>
      </div>
    </div>
  )
}
