import axios from 'axios'

/**
 * Read the message out of a refusal.
 *
 * The API answers errors as `{"detail": {"message": ...}}` and that message is
 * written to be content-free, so it is safe to show as-is. Older shapes and
 * network failures fall back to the caller's wording.
 */
export function errorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback

  const data = error.response?.data
  return data?.detail?.message || data?.message || fallback
}
