import { Icon } from './Icon'

interface Props {
  documentCount: number
  onStartOver: () => void
}

export function EmptySummary({ documentCount, onStartOver }: Props) {
  const subject = documentCount === 1 ? 'ce document' : 'ces documents'

  return (
    <div className="flex flex-col items-center gap-3.5 rounded-[10px] border border-rule bg-surface px-8 py-[34px]">
      <Icon name="documentBlank" size={28} strokeWidth={1.4} className="text-source" />
      <span className="text-[17px] font-semibold text-ink">Rien à résumer</span>
      <p
        role="status"
        className="max-w-[460px] text-center text-sm leading-[1.6] text-pretty text-ink-muted"
      >
        Aucun élément clinique n&apos;a été reconnu dans {subject}. La lecture a bien eu
        lieu : ni pathologie, ni symptôme, ni examen, ni traitement n&apos;y figure. Une
        lettre administrative ou un formulaire de consentement donne ce résultat.
      </p>
      <button
        type="button"
        onClick={onStartOver}
        className="h-11 cursor-pointer rounded-lg border border-accent bg-accent px-[22px] text-sm font-semibold text-surface hover:bg-accent-strong"
      >
        Choisir d&apos;autres documents
      </button>
    </div>
  )
}
