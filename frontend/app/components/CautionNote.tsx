import { Icon } from './Icon'

interface Props {
  children: string
}

/** The ochre bar. One per screen, and never more than one sentence of it. */
export function CautionNote({ children }: Props) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-caution-edge bg-caution-tint px-[18px] py-4">
      <Icon
        name="warning"
        size={18}
        strokeWidth={1.7}
        className="mt-px shrink-0 text-caution"
      />
      <span className="text-[13.5px] leading-[1.55] text-pretty text-caution-ink">
        {children}
      </span>
    </div>
  )
}
