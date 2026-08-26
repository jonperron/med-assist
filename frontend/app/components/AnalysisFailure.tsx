import { Icon } from './Icon'

interface Props {
  message: string
  onRetry: () => void
  onStartOver: () => void
}

/**
 * The refusal, shown whole.
 *
 * The backend answers a batch it could not read with one fixed, content-free
 * message and deliberately does not name the file that failed, so this card
 * cannot either: it reports that no summary was produced, not that one
 * document out of several was skipped.
 */
export function AnalysisFailure({ message, onRetry, onStartOver }: Props) {
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
          Aucun résumé n&apos;a pu être établi
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
