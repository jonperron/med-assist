import type { StreamFailure } from '../lib/analysisStream'
import { Icon } from './Icon'

interface Props {
  message: string
  /** Which kind of failure this is, for the headline above the message. */
  reason: StreamFailure
  /**
   * False while the service has said it cannot analyse. The retry would send
   * the same batch to a backend known to refuse it, and an enabled control
   * beside a disabled submit button reads as the interface contradicting
   * itself - this is the state where the two most need to agree.
   */
  canRetry?: boolean
  onRetry: () => void
  onStartOver: () => void
}

// Four different things to tell a clinician: their scans did not work, they
// sent more than can be analysed, the service did not work, or the answer
// never arrived. Only the first is worth trying another scan for, and only the
// second is fixed by changing the selection.
const HEADLINES: Record<StreamFailure, string> = {
  unreadable_batch: "Aucun résumé n'a pu être établi",
  too_large: 'Cet envoi dépasse ce qui peut être analysé',
  server_error: "L'analyse n'a pas abouti",
  transport: "L'analyse s'est interrompue",
  unauthorized: "Ce service n'est pas accessible depuis cette interface",
}

// A batch refused for its size will be refused identically next time, so the
// retry is a control that does nothing. The clinician's move is to change the
// selection, which is the other button.
// A credential refusal is the other one that cannot be retried, and for a
// firmer reason than size: this interface has no credential to present and no
// way to obtain one, so the same request will be refused identically for as
// long as the deployment is configured that way. Retrying is a control that
// does nothing, and offering it reads as the failure being transient.
const RETRYABLE: Record<StreamFailure, boolean> = {
  unreadable_batch: true,
  too_large: false,
  server_error: true,
  transport: true,
  unauthorized: false,
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

/** A reason this build does not know is offered the retry, like a transport. */
function retryable(reason: StreamFailure): boolean {
  return Object.hasOwn(RETRYABLE, reason) ? RETRYABLE[reason] : true
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
export function AnalysisFailure({
  message,
  reason,
  canRetry = true,
  onRetry,
  onStartOver,
}: Props) {
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
          {retryable(reason) && canRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="h-11 cursor-pointer rounded-lg border border-edge bg-surface px-5 text-sm font-semibold text-ink hover:bg-paper"
            >
              Réessayer
            </button>
          )}
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
