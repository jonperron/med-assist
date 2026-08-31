/**
 * The build's version, and where to report what it gets wrong.
 *
 * `package.json` is the single source of truth for the number. It is not
 * imported here: that would pull the whole manifest - every dependency and its
 * range - into the client bundle to read one string. `next.config.ts` reads the
 * manifest at build time and injects the value, so what ships is a literal.
 *
 * The fallback covers the environments that have no Next build behind them,
 * which today is the test runner before `vitest.config.ts` defines the value.
 * A clinician never sees it; a developer reading `dev` in the footer is being
 * told the truth about what they are looking at.
 */
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || 'dev'

/**
 * Where a clinician reports a problem. The repository is public and holds no
 * patient data, which is what makes it a safe address to put in front of one -
 * and why the footer asks for a description of the problem rather than for the
 * document that caused it.
 */
export const ISSUES_URL = 'https://github.com/jonperron/med-assist/issues'
