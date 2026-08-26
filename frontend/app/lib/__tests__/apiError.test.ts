import { describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { errorMessage } from '../apiError'

vi.mock('axios')

const mockedAxios = vi.mocked(axios, true)

function axiosErrorWith(data: unknown) {
  mockedAxios.isAxiosError.mockReturnValue(true)
  return { isAxiosError: true, response: { data } }
}

const FALLBACK = 'Échec.'

describe('errorMessage', () => {
  it('reads the documented envelope', () => {
    expect(errorMessage(axiosErrorWith({ detail: { message: 'Refusé.' } }), FALLBACK)).toBe(
      'Refusé.'
    )
  })

  it('falls back for anything that is not an axios error', () => {
    mockedAxios.isAxiosError.mockReturnValue(false)
    expect(errorMessage(new Error('boom'), FALLBACK)).toBe(FALLBACK)
  })

  it('refuses a message that is not a string', () => {
    expect(errorMessage(axiosErrorWith({ detail: { message: { a: 1 } } }), FALLBACK)).toBe(
      FALLBACK
    )
    expect(errorMessage(axiosErrorWith({ detail: { message: ['a'] } }), FALLBACK)).toBe(
      FALLBACK
    )
  })

  it('refuses an empty or blank message', () => {
    expect(errorMessage(axiosErrorWith({ detail: { message: '   ' } }), FALLBACK)).toBe(
      FALLBACK
    )
  })

  it('refuses an upstream string too long to be one of ours', () => {
    const wall = 'x'.repeat(500)
    expect(errorMessage(axiosErrorWith({ detail: { message: wall } }), FALLBACK)).toBe(
      FALLBACK
    )
  })

  it('refuses an HTML error page from a proxy', () => {
    expect(errorMessage(axiosErrorWith('<html>502 Bad Gateway</html>'), FALLBACK)).toBe(
      FALLBACK
    )
  })
})
