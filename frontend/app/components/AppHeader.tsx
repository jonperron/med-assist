import type { ReactNode } from 'react'
import { Icon } from './Icon'

interface Props {
  /** The right-hand slot: the privacy badge, or the summary's own actions. */
  children?: ReactNode
}

export function AppHeader({ children }: Props) {
  return (
    <header
      data-print="hide"
      className="flex h-16 items-center justify-between gap-6 border-b border-rule bg-surface px-10"
    >
      <div className="flex items-center gap-3.5">
        <Icon name="stethoscope" size={20} className="text-accent" />
        <span className="font-serif text-[19px] tracking-[-0.01em] text-ink">
          Med-Assist
        </span>
      </div>
      {children}
    </header>
  )
}
