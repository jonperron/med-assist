import type { JSX } from 'react'

// The whole icon set, drawn on one 24x24 grid at one stroke weight so a row of
// them reads as a single family. Colour comes from `currentColor`, so an icon
// takes the text colour of whatever it sits in and never needs its own token.
const PATHS: Record<string, JSX.Element> = {
  stethoscope: (
    <>
      <path d="M6 3v5a5 5 0 0 0 10 0V3" />
      <path d="M11 13v2a4 4 0 0 0 8 0v-1" />
      <circle cx="19" cy="13" r="2.2" />
    </>
  ),
  shield: <path d="M12 3l7 3v6c0 4.2-2.8 7.6-7 9-4.2-1.4-7-4.8-7-9V6z" />,
  upload: (
    <>
      <path d="M12 15V4" />
      <path d="M8 8l4-4 4 4" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  document: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </>
  ),
  documentBlank: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 14h6" />
    </>
  ),
  close: (
    <>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </>
  ),
  check: <path d="M20 6L9 17l-5-5" />,
  spinner: <path d="M12 3a9 9 0 1 0 9 9" />,
  circle: <circle cx="12" cy="12" r="9" />,
  warning: (
    <>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9L2.6 17.1A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </>
  ),
  printer: (
    <>
      <path d="M7 9V4h10v5" />
      <rect x="4" y="9" width="16" height="7" rx="2" />
      <path d="M7 14h10v6H7z" />
    </>
  ),
}

export type IconName = keyof typeof PATHS

interface Props {
  name: IconName
  size?: number
  strokeWidth?: number
  className?: string
}

export function Icon({ name, size = 18, strokeWidth = 1.6, className }: Props) {
  return (
    <svg
      // Decorative throughout: every icon in this interface sits beside a
      // label that already says the same thing, so announcing it would only
      // make a screen reader repeat itself.
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {PATHS[name]}
    </svg>
  )
}
