/**
 * The Content-Security-Policy that makes the local-first claim enforceable.
 *
 * `PrivacyBadge` tells the clinician their documents stay on this machine.
 * Without a policy that is a promise about intent: any script on the page
 * could open a connection to a third party and the browser would allow it.
 * `connect-src` is the directive that closes that, which is why it names
 * exactly two origins - the page itself and the backend - and why this module
 * exists.
 *
 * What it closes is every silent channel: fetch, XHR, EventSource, WebSocket,
 * sendBeacon, a remote image used as a beacon, an off-origin form post. What no
 * CSP closes is a deliberate navigation - assigning `location.href` is governed
 * by no directive any browser ships. So the guarantee is "nothing leaves
 * quietly", not "nothing can leave".
 *
 * Kept out of `next.config.ts` so the policy can be unit-tested. The config
 * imports `securityHeaders` and serves what it returns.
 */

/**
 * Matches the repository-root `.env.example` and the fallback `app/page.tsx`
 * uses for the fetch itself.
 */
export const DEFAULT_API_URL = 'http://localhost:8000'

/**
 * A hostname a CSP source expression may safely carry: letters, digits and
 * hyphens in dot-separated labels, or a bracketed IPv6 literal. An IPv4
 * address satisfies the first form.
 *
 * The URL parser is not this strict. `*` and `;` are not forbidden domain code
 * points, so `http://*.example.org` and `http://host;sandbox` both parse and
 * both reach `URL.origin` verbatim - the first widening `connect-src` to every
 * subdomain, the second ending the directive early and appending one the
 * policy never intended. Neither is a value anyone types by accident, which is
 * the point: an environment variable is an injection surface for whatever can
 * set it.
 */
const SAFE_HOSTNAME =
  /^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*\.?)$/

export interface SecurityPolicyOptions {
  /**
   * The value of `NEXT_PUBLIC_API_URL`. Undefined and empty both mean "not
   * configured" and fall back to {@link DEFAULT_API_URL}; anything else must
   * parse, because a policy built from a broken value would ship a page that
   * cannot reach its own backend.
   */
  apiUrl?: string
  /**
   * True only for `next dev`, which needs `eval` for React Fast Refresh and a
   * websocket for hot reload. It defaults to false so that anything which
   * forgets to pass it gets the strict policy: the relaxations have to be
   * asked for, and cannot be inherited.
   */
  development?: boolean
}

export interface SecurityHeader {
  key: string
  value: string
}

/**
 * What a rejected value may be quoted as in a build error.
 *
 * The operator needs to see which variable is wrong and roughly what shape it
 * had. They do not need it reflected back in full: a mistyped scheme on a URL
 * carrying credentials would otherwise put those credentials in a build log,
 * which is usually more widely readable than the artefact.
 */
function quoteForError(value: string): string {
  const trimmed = value.length > 60 ? `${value.slice(0, 60)}...` : value
  return JSON.stringify(trimmed)
}

/**
 * The configured API base, trimmed, with the default standing in for an unset
 * or blank value.
 *
 * Exported so the page fetches from exactly the value the policy was built for.
 * They used to derive it separately - this trimmed, `page.tsx` did not - and a
 * whitespace-only `NEXT_PUBLIC_API_URL` is truthy: the policy would be built
 * for the default origin while `fetch` received a blank base and resolved the
 * analysis POST against the frontend's own origin, sending a clinician's
 * documents to the Next server rather than to the API.
 *
 * The whole base is returned rather than {@link apiOrigin}'s origin, because
 * this is what a path is appended to: reducing it here would silently drop a
 * path prefix from a deployment that configured one.
 */
export function apiBaseUrl(apiUrl?: string): string {
  return apiUrl?.trim() || DEFAULT_API_URL
}

/**
 * The origin of the configured API, and nothing else from the URL.
 *
 * A CSP source expression is an origin: scheme, host, port. Passing a whole
 * URL would put a path into the directive, which the browser reads as a path
 * restriction on every request - a subtly narrower policy than intended.
 *
 * @throws Error when the value is not an absolute http(s) URL with a plain
 * hostname. The build stops rather than emitting a directive nobody would
 * notice was wrong until a clinician's analysis failed in the browser.
 */
export function apiOrigin(apiUrl?: string): string {
  const configured = apiBaseUrl(apiUrl)

  let parsed: URL
  try {
    parsed = new URL(configured)
  } catch {
    throw new Error(
      `NEXT_PUBLIC_API_URL is not an absolute URL: ${quoteForError(configured)}. ` +
        `Expected something like ${DEFAULT_API_URL}.`
    )
  }

  // `new URL('localhost:8000')` parses, with `localhost:` as its scheme. The
  // scheme is therefore checked before anything else is trusted about it.
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(
      `NEXT_PUBLIC_API_URL must use http or https, not ${JSON.stringify(parsed.protocol)}. ` +
        `Expected something like ${DEFAULT_API_URL}.`
    )
  }

  if (!SAFE_HOSTNAME.test(parsed.hostname)) {
    throw new Error(
      `NEXT_PUBLIC_API_URL has no usable host: ${quoteForError(configured)}. ` +
        `A host may carry letters, digits, hyphens and dots, or be a bracketed ` +
        `IPv6 address. Expected something like ${DEFAULT_API_URL}.`
    )
  }

  return parsed.origin
}

/**
 * Build the policy as a single header value.
 *
 * Every directive here was checked against a production build rather than
 * assumed:
 *
 * - `script-src` carries `'unsafe-inline'` because Next serialises the React
 *   payload into inline `<script>` elements in the rendered HTML. Removing it
 *   needs a per-request nonce, which needs middleware. That used to cost making
 *   every route dynamic, which is why it was not done - and that cost is now
 *   already paid: `app/layout.tsx` declares `force-dynamic` so the deployment
 *   warning can be read from the environment at request time. Tightening this
 *   is a real option again, and the reason it has not been taken is that
 *   nobody has done the work, not that the price is too high.
 *   `'unsafe-eval'` is not granted in production.
 * - `style-src` carries `'unsafe-inline'` because the error and not-found
 *   routes ship a `<style>` element and inline `style` attributes, and the
 *   reading progress bar sets its width through an inline style at runtime.
 * - `font-src 'self'` holds because `next/font` self-hosts both faces under
 *   `/_next/static/media`; the built HTML references no external origin.
 * - `img-src` allows `data:` alongside `'self'`. Nothing in the interface
 *   needs it today - every icon is an inline `<svg>` element and the favicon
 *   is same-origin - so it is headroom rather than a requirement. A data URI
 *   issues no request, so it is not an egress channel.
 */
export function contentSecurityPolicy(options: SecurityPolicyOptions = {}): string {
  const { development = false } = options
  const backend = apiOrigin(options.apiUrl)

  const scriptSources = ["'self'", "'unsafe-inline'"]
  const connectSources = ["'self'", backend]

  if (development) {
    // Fast Refresh compiles modules in the browser.
    scriptSources.push("'unsafe-eval'")
    // Turbopack's hot-reload channel, on whichever port the dev server picked.
    // Named explicitly rather than as a bare `ws:` scheme source: a bare scheme
    // matches every host on that scheme, which is the egress this policy exists
    // to refuse.
    connectSources.push('ws://localhost:*', 'ws://127.0.0.1:*', 'ws://[::1]:*')
  }

  const directives: ReadonlyArray<readonly [string, readonly string[]]> = [
    ['default-src', ["'self'"]],
    ['base-uri', ["'self'"]],
    ['form-action', ["'self'"]],
    ['frame-ancestors', ["'none'"]],
    ['object-src', ["'none'"]],
    ['script-src', scriptSources],
    ['style-src', ["'self'", "'unsafe-inline'"]],
    ['img-src', ["'self'", 'data:']],
    ['font-src', ["'self'"]],
    ['connect-src', connectSources],
  ]

  return directives
    .map(([name, sources]) => `${name} ${sources.join(' ')}`)
    .join('; ')
}

/**
 * The policy plus the headers that belong beside it.
 *
 * No `Strict-Transport-Security`: the stack is served over plain HTTP on
 * localhost, and an HSTS header would pin the clinician's browser to HTTPS for
 * that host long after this application is gone.
 */
export function securityHeaders(
  options: SecurityPolicyOptions = {}
): ReadonlyArray<SecurityHeader> {
  return [
    { key: 'Content-Security-Policy', value: contentSecurityPolicy(options) },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    // The page must not name itself to anywhere it navigates. There is no
    // analytics sink, and the one outbound link - the footer's issue tracker -
    // does not need attribution: it carries `rel="noreferrer"` of its own, so
    // the two hold independently rather than one relying on the other.
    { key: 'Referrer-Policy', value: 'no-referrer' },
    // `frame-ancestors 'none'` above is the real control; this is for agents
    // that do not implement it.
    { key: 'X-Frame-Options', value: 'DENY' },
  ]
}
