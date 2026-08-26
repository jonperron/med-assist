import axios from 'axios'

// A refusal is rendered as Med-Assist's own wording, so an upstream string of
// any length would read as something this app said. The backend's messages are
// all short fixed constants; anything longer is not one of them.
const MAX_MESSAGE_LENGTH = 300

function usable(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

/**
 * Read the message out of a refusal.
 *
 * The API answers errors as `{"detail": {"message": ...}}` and every message
 * behind that shape is a fixed, content-free constant, so it is safe to show.
 * Anything else - a proxy's error envelope, an HTML page, a body where
 * `message` is not a string - falls back to the caller's wording rather than
 * putting an unknown upstream string in front of a clinician.
 */
export function errorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback

  const data = error.response?.data
  const candidate: unknown = data?.detail?.message ?? data?.message

  if (!usable(candidate) || candidate.length > MAX_MESSAGE_LENGTH) return fallback

  return candidate
}
