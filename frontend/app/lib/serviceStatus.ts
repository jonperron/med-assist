/**
 * Whether the backend can analyse anything right now.
 *
 * The model is read once at startup and the routes that need it answer 503
 * until it is in memory. Without this the only way a clinician learned that was
 * to select their documents, submit them, and get a refusal back - which reads
 * as their scans having failed rather than as the service not being up. Asking
 * `GET /readyz` before they start moves that to the top of the screen.
 *
 * Nothing about *why* crosses this boundary, and nothing should: the endpoint
 * answers a fixed string with no path and no configuration in it, and the
 * interface says the service is unavailable without naming what it is missing.
 */

/** The path the backend answers readiness on. */
export const READY_PATH = '/readyz'

/**
 * What the last check established.
 *
 * The two failing states are kept apart because they justify different amounts
 * of interference:
 *
 * - `unavailable` is the service answering for itself - it is up, and it says
 *   it cannot analyse. That is authoritative, so the interface acts on it.
 * - `unreachable` is the absence of an answer: a network error, a check that
 *   ran out of time, a 404 from a deployment that does not route `/readyz`, a
 *   proxy's 405. Something is wrong, but nothing has established that an
 *   analysis would fail, so this reports without taking a control away.
 *
 * `unknown` is the state before the first answer, and it is neither: a warning
 * rendered during the first round trip would flash on every load of a perfectly
 * healthy deployment.
 */
export type ServiceStatus = 'unknown' | 'ready' | 'unavailable' | 'unreachable'

// How long before asking again. A service that is down is polled briskly
// because it is a state the clinician is waiting out - a cold start is seconds,
// and the banner clearing by itself is the whole point of polling rather than
// checking once. Ready is polled slowly: it only has to notice a backend that
// went away, and the analysis path reports that on its own if one does while a
// batch is in flight.
const WHILE_DOWN_MS = 5_000
const WHILE_READY_MS = 30_000

// A check that never settles must not be able to stop the loop. The poll
// schedules its next run only once the previous one has answered, so without a
// deadline a single hung request freezes the interface in whatever state it was
// last in - and if that state is `unavailable`, nothing short of a reload gets
// the clinician moving again. Kept under WHILE_DOWN_MS so two checks are never
// in flight at once.
const CHECK_TIMEOUT_MS = 4_000

/** How long to wait before the next check, given what the last one said. */
export function nextCheckDelay(status: ServiceStatus): number {
  return status === 'ready' ? WHILE_READY_MS : WHILE_DOWN_MS
}

/**
 * Whether the interface should still let a clinician submit a batch.
 *
 * Only the service's own refusal closes the door. Not knowing is not the same
 * as knowing the answer is no: a deployment that does not route `/readyz` would
 * otherwise have its analysis path - which works - permanently disabled by a
 * probe that does not.
 */
export function canAnalyse(status: ServiceStatus): boolean {
  return status !== 'unavailable'
}

/**
 * Ask the backend whether it can analyse a document.
 *
 * @param baseUrl Where the API is, without a trailing path.
 * @param signal Aborts the check when the page stops caring about the answer.
 * @returns One of {@link ServiceStatus}, never `unknown`. Never throws,
 *   including on abort or timeout - the caller checks its own signal rather
 *   than distinguishing an abort here.
 */
export async function checkService(
  baseUrl: string,
  signal?: AbortSignal
): Promise<ServiceStatus> {
  // Composed by hand rather than with `AbortSignal.any`, which is recent enough
  // that a browser without it would throw here - inside the one function whose
  // whole job is to not fail.
  const deadline = new AbortController()
  const expire = setTimeout(() => deadline.abort(), CHECK_TIMEOUT_MS)
  const giveUp = () => deadline.abort()
  signal?.addEventListener('abort', giveUp)

  try {
    const response = await fetch(`${baseUrl}${READY_PATH}`, {
      method: 'GET',
      // The answer is a flag that changes underneath the client by design.
      // A cached 503 would leave the warning up for a service that came ready
      // seconds later, which is the one thing this must not do.
      cache: 'no-store',
      signal: deadline.signal,
    })

    if (response.ok) return 'ready'

    // A 5xx is the service reporting on itself, and 503 is the one the
    // readiness gate sends while the model is not in memory. Anything else -
    // a 404, a proxy's 405 - is a deployment this client cannot interpret, and
    // guessing that it means "cannot analyse" would disable a working service.
    return response.status >= 500 ? 'unavailable' : 'unreachable'
  } catch {
    // A network error, a CORS refusal, the deadline, or the caller's abort.
    // None of them are an answer, and none of them are a reason to claim the
    // service is up - or to claim it has refused.
    return 'unreachable'
  } finally {
    clearTimeout(expire)
    signal?.removeEventListener('abort', giveUp)
  }
}
