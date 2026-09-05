/**
 * Whether this deployment is the unsecured, publicly reachable kind.
 *
 * The API authenticates nobody. On the machine it was written for that is
 * unremarkable - the only caller is the person sitting in front of it. Served
 * from a public address it is a different statement entirely, and one the
 * interface has to make out loud: anyone can reach the service, and a document
 * submitted through it is exposed to whoever else is looking.
 *
 * The flag is a plain environment variable rather than a `NEXT_PUBLIC_` one on
 * purpose. `NEXT_PUBLIC_*` values are inlined into the bundle at build time, so
 * turning the warning on would mean rebuilding and republishing the image -
 * which is exactly the friction that ends with a public deployment running
 * without it. Read at request time, an operator sets one variable and restarts.
 *
 * It is the operator's own configuration, not a caller's input, so it is
 * trusted as such - and it fails towards the warning being shown rather than
 * hidden only where the value is unambiguous.
 */

/** The variable an operator sets. Named once so the docs and the code agree. */
export const UNSECURED_DEPLOYMENT_VARIABLE = 'UNSECURED_DEPLOYMENT'

// What counts as "on". Spelled out rather than treating any non-empty string as
// true, because `UNSECURED_DEPLOYMENT=false` is a thing an operator writes and
// reading it as true would be absurd - and `UNSECURED_DEPLOYMENT=off` is a
// thing they write when they mean it.
const ENABLED = new Set(['1', 'true', 'yes', 'on'])

/**
 * Read the flag.
 *
 * @param raw The variable's value, or undefined when it is not set.
 * @returns Whether the interface should warn that this deployment is open.
 */
export function unsecuredDeployment(raw: string | undefined): boolean {
  if (raw === undefined) return false
  return ENABLED.has(raw.trim().toLowerCase())
}
