'use client'

import { useEffect, useState } from 'react'

interface Props {
  expiresInSeconds: number
}

export function formatRemaining(seconds: number): string {
  if (seconds < 60) return `${seconds}s`

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min`

  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}min`
}

export default function RetentionNotice({ expiresInSeconds }: Props) {
  const [remaining, setRemaining] = useState(expiresInSeconds)

  useEffect(() => {
    // Count down against a fixed deadline rather than decrementing a counter,
    // so a throttled or suspended tab does not drift behind the server.
    const deadline = Date.now() + expiresInSeconds * 1000
    const timer = setInterval(() => {
      setRemaining(Math.max(Math.round((deadline - Date.now()) / 1000), 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [expiresInSeconds])

  return (
    <p role="status" className="mt-2 text-sm text-gray-600">
      {remaining > 0
        ? `This document is deleted from the server in ${formatRemaining(remaining)}.`
        : 'This document has been deleted from the server.'}
    </p>
  )
}
