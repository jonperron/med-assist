import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import RetentionNotice, { formatRemaining } from '../RetentionNotice'

describe('formatRemaining', () => {
  it('renders seconds below a minute', () => {
    expect(formatRemaining(45)).toBe('45s')
  })

  it('renders whole minutes below an hour', () => {
    expect(formatRemaining(3599)).toBe('59 min')
  })

  it('renders hours and minutes above an hour', () => {
    expect(formatRemaining(3600)).toBe('1h 0min')
    expect(formatRemaining(5460)).toBe('1h 31min')
  })
})

describe('RetentionNotice', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('announces when the document disappears', () => {
    render(<RetentionNotice expiresInSeconds={3600} />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'This document is deleted from the server in 1h 0min.'
    )
  })

  it('counts down as time passes', () => {
    render(<RetentionNotice expiresInSeconds={65} />)
    act(() => {
      vi.advanceTimersByTime(6000)
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'This document is deleted from the server in 59s.'
    )
  })

  it('reports the document as gone once the window closes', () => {
    render(<RetentionNotice expiresInSeconds={2} />)
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'This document has been deleted from the server.'
    )
  })
})
