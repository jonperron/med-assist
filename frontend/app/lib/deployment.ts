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
 * trusted as such - and once set, it fails towards the warning being shown.
 */

/** The variable an operator sets. Named once so the docs and the code agree. */
export const UNSECURED_DEPLOYMENT_VARIABLE = 'UNSECURED_DEPLOYMENT'

// What counts as "off" once the variable is set to something. Spelled out as a
// closed list because `UNSECURED_DEPLOYMENT=false` is a thing an operator
// writes and reading it as true would be absurd.
//
// Everything else that is not blank counts as on, and the asymmetry is the
// point. An unset variable is the local default and means off. A variable an
// operator *set*, to a value this does not recognise - `oui`, `y`, `enabled`,
// `ture` - is an operator who has already decided the deployment is public and
// has misspelled the switch. Reading that as off loses the only warning a
// clinician gets, restores a badge claiming the documents stay on their
// machine, and logs nothing. Reading it as on shows a banner somebody did not
// quite ask for, which is a bad afternoon rather than a bad outcome.
const DISABLED = new Set(['0', 'false', 'no', 'off'])

/**
 * Read the flag.
 *
 * @param raw The variable's value, or undefined when it is not set.
 * @returns Whether the interface should warn that this deployment is open.
 */
export function unsecuredDeployment(raw: string | undefined): boolean {
  if (raw === undefined) return false
  const value = raw.trim().toLowerCase()
  if (value === '') return false
  return !DISABLED.has(value)
}
