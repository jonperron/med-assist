import { describe, expect, it } from 'vitest'
import {
  DEFAULT_API_URL,
  apiBaseUrl,
  apiOrigin,
  contentSecurityPolicy,
  securityHeaders,
} from '../contentSecurityPolicy'

function directive(policy: string, name: string): string {
  const found = policy
    .split(';')
    .map(part => part.trim())
    .find(part => part === name || part.startsWith(`${name} `))

  if (found === undefined) {
    throw new Error(`no ${name} directive in ${policy}`)
  }

  return found
}

describe('apiBaseUrl', () => {
  it('is what the page fetches from, so the policy and the request agree', () => {
    expect(apiBaseUrl('https://med-assist.example.org')).toBe(
      'https://med-assist.example.org'
    )
  })

  it('falls back for a value that is only whitespace', () => {
    // The page used to take this value behind a bare falsy check, where a
    // whitespace string is truthy: the policy was built for the default origin
    // while `fetch` got a blank base and resolved the analysis POST against the
    // frontend's own origin - a clinician's documents to the wrong server.
    expect(apiBaseUrl('   ')).toBe(DEFAULT_API_URL)
    expect(apiBaseUrl('')).toBe(DEFAULT_API_URL)
    expect(apiBaseUrl(undefined)).toBe(DEFAULT_API_URL)
  })

  it('keeps a path prefix that the origin would drop', () => {
    // This is the base a path is appended to, not a CSP source expression.
    // Reducing it to an origin here would silently unconfigure a deployment
    // served under a prefix.
    expect(apiBaseUrl('https://example.org/backend')).toBe(
      'https://example.org/backend'
    )
  })

  it('is the value apiOrigin resolves, so the two cannot drift', () => {
    expect(apiOrigin('  https://example.org:8443/ignored  ')).toBe(
      new URL(apiBaseUrl('  https://example.org:8443/ignored  ')).origin
    )
  })
})

describe('apiOrigin', () => {
  it('keeps the origin and drops the path', () => {
    expect(apiOrigin('http://localhost:8000/api/analyze')).toBe('http://localhost:8000')
  })

  it('preserves a non-default port', () => {
    expect(apiOrigin('http://backend.internal:9443')).toBe('http://backend.internal:9443')
  })

  it('drops a query string and a fragment', () => {
    expect(apiOrigin('https://api.example.org/v1?token=x#frag')).toBe(
      'https://api.example.org'
    )
  })

  it('falls back to the documented default when unset or empty', () => {
    expect(apiOrigin(undefined)).toBe(DEFAULT_API_URL)
    expect(apiOrigin('')).toBe(DEFAULT_API_URL)
    expect(apiOrigin('   ')).toBe(DEFAULT_API_URL)
  })

  it('throws on a relative value', () => {
    expect(() => apiOrigin('/api')).toThrow(/NEXT_PUBLIC_API_URL/)
  })

  it('throws on a host with no scheme', () => {
    // `new URL('localhost:8000')` parses with `localhost:` as its scheme, so
    // this is the case a naive parse lets through as the origin `null`.
    expect(() => apiOrigin('localhost:8000')).toThrow(/NEXT_PUBLIC_API_URL/)
  })

  it('throws on a non-http scheme', () => {
    expect(() => apiOrigin('ftp://example.org')).toThrow(/http or https/)
  })

  it('throws on nonsense', () => {
    expect(() => apiOrigin('not a url')).toThrow(/NEXT_PUBLIC_API_URL/)
  })

  it('refuses a wildcard host rather than widening the directive', () => {
    // `*` is not a forbidden domain code point, so the URL parser accepts this
    // and `URL.origin` hands it back verbatim. Unchecked it would authorise
    // every subdomain of example.org.
    expect(() => apiOrigin('http://*.example.org')).toThrow(/no usable host/)
    expect(() => apiOrigin('http://*')).toThrow(/no usable host/)
  })

  it('refuses a host that would inject a second directive', () => {
    // A semicolon in the host ends connect-src early and starts a directive of
    // the attacker's choosing. `sandbox` and `upgrade-insecure-requests` both
    // take no value, so both are syntactically complete on their own.
    expect(() => apiOrigin('http://host;sandbox')).toThrow(/no usable host/)
    expect(() => apiOrigin('http://host;upgrade-insecure-requests')).toThrow(
      /no usable host/
    )
  })

  it('accepts the address forms a local deployment actually uses', () => {
    expect(apiOrigin('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
    expect(apiOrigin('http://[::1]:8000')).toBe('http://[::1]:8000')
    expect(apiOrigin('https://med-assist.internal')).toBe('https://med-assist.internal')
  })

  it('does not echo a rejected value back in full', () => {
    // NEXT_PUBLIC_API_URL is inlined into the client bundle, so it is not a
    // secret - but a build log is usually more widely readable than the
    // artefact, and a mistyped scheme can carry credentials.
    const long = `ftp://user:hunter2@${'a'.repeat(200)}.example.org`

    expect(() => apiOrigin(long)).toThrow(/http or https/)
    expect(() => apiOrigin(long)).not.toThrow(/hunter2/)
  })
})

describe('contentSecurityPolicy', () => {
  it('names the configured API origin in connect-src, and nothing else', () => {
    const policy = contentSecurityPolicy({ apiUrl: 'http://localhost:8000' })

    expect(directive(policy, 'connect-src')).toBe(
      "connect-src 'self' http://localhost:8000"
    )
  })

  it('contributes only the origin of an API URL that carries a path', () => {
    const policy = contentSecurityPolicy({
      apiUrl: 'https://med.example.org:8443/api/analyze/stream',
    })

    expect(directive(policy, 'connect-src')).toBe(
      "connect-src 'self' https://med.example.org:8443"
    )
    expect(policy).not.toContain('/api/analyze')
  })

  it('falls back to the documented default when the variable is unset', () => {
    expect(directive(contentSecurityPolicy(), 'connect-src')).toBe(
      `connect-src 'self' ${DEFAULT_API_URL}`
    )
  })

  it('fails loudly on a malformed API URL rather than emitting a broken directive', () => {
    expect(() => contentSecurityPolicy({ apiUrl: 'http://' })).toThrow(
      /NEXT_PUBLIC_API_URL/
    )
  })

  it('never widens a directive to a wildcard', () => {
    const policies = [
      contentSecurityPolicy(),
      contentSecurityPolicy({ development: true }),
      contentSecurityPolicy({ apiUrl: 'https://api.example.org' }),
    ]

    for (const policy of policies) {
      for (const part of policy.split(';')) {
        const sources = part.trim().split(/\s+/).slice(1)

        expect(sources).not.toContain('*')
        // A wildcard is only ever allowed to stand for a port. A host that
        // ends in one - `ws://*` or `https://*.example.org` - authorises a set
        // of origins rather than an origin.
        for (const source of sources) {
          expect(source.replace(/:\*$/, '')).not.toContain('*')
        }
      }
    }
  })

  it('grants no bare-scheme source outside development', () => {
    // A bare scheme source such as `ws:` or `https:` matches every host on that
    // scheme. One of those in connect-src would reopen exactly the egress this
    // policy exists to refuse, so the production policy must carry none at all.
    const policy = contentSecurityPolicy({ apiUrl: 'https://api.example.org' })

    for (const part of policy.split(';')) {
      const sources = part.trim().split(/\s+/).slice(1)
      const bareSchemes = sources.filter(
        source => /^[a-z][a-z0-9+.-]*:$/.test(source) && source !== 'data:'
      )

      expect(bareSchemes).toEqual([])
    }
  })

  it('defaults to the strict policy when nobody says which environment it is', () => {
    // The relaxations have to be asked for. A caller that forgets the flag must
    // not silently get the development policy.
    const policy = contentSecurityPolicy()

    expect(policy).not.toContain("'unsafe-eval'")
    expect(policy).not.toContain('ws:')
  })

  it('scopes the development hot-reload socket to the local host', () => {
    const policy = contentSecurityPolicy({ development: true })

    expect(directive(policy, 'connect-src')).toBe(
      `connect-src 'self' ${DEFAULT_API_URL} ws://localhost:* ws://127.0.0.1:* ws://[::1]:*`
    )
    // The port varies with whatever the dev server picked; the host must not.
    expect(policy).not.toMatch(/\bws:(?!\/\/)/)
    expect(policy).not.toContain('wss:')
  })

  it('keeps the inline styles the interface depends on', () => {
    // ReadingProgress sets the bar width through an inline style attribute, and
    // global-error.tsx is inline styles throughout. Tightening this directive
    // would break the reading screen with the suite still green.
    expect(directive(contentSecurityPolicy(), 'style-src')).toBe(
      "style-src 'self' 'unsafe-inline'"
    )
  })

  it('locks down the framing, base and form boundaries', () => {
    const policy = contentSecurityPolicy()

    expect(directive(policy, 'default-src')).toBe("default-src 'self'")
    expect(directive(policy, 'frame-ancestors')).toBe("frame-ancestors 'none'")
    expect(directive(policy, 'object-src')).toBe("object-src 'none'")
    expect(directive(policy, 'base-uri')).toBe("base-uri 'self'")
    expect(directive(policy, 'form-action')).toBe("form-action 'self'")
  })

  it('keeps fonts and images local, allowing only inline image data', () => {
    const policy = contentSecurityPolicy()

    expect(directive(policy, 'font-src')).toBe("font-src 'self'")
    expect(directive(policy, 'img-src')).toBe("img-src 'self' data:")
  })

  it('never grants eval to a production build', () => {
    const policy = contentSecurityPolicy({ apiUrl: 'https://api.example.org' })

    expect(policy).not.toContain("'unsafe-eval'")
    expect(directive(policy, 'script-src')).toBe("script-src 'self' 'unsafe-inline'")
  })

  it('grants the development server eval', () => {
    const policy = contentSecurityPolicy({ development: true })

    expect(directive(policy, 'script-src')).toBe(
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    )
  })
})

describe('securityHeaders', () => {
  it('serves the policy alongside its conventional companions', () => {
    const headers = securityHeaders({ apiUrl: 'http://localhost:8000' })
    const byKey = new Map(headers.map(header => [header.key, header.value]))

    expect(byKey.get('Content-Security-Policy')).toContain(
      "connect-src 'self' http://localhost:8000"
    )
    expect(byKey.get('X-Content-Type-Options')).toBe('nosniff')
    expect(byKey.get('Referrer-Policy')).toBe('no-referrer')
    expect(byKey.get('X-Frame-Options')).toBe('DENY')
  })

  it('does not pin the browser to HTTPS on a plain-HTTP local stack', () => {
    const keys = securityHeaders().map(header => header.key.toLowerCase())

    expect(keys).not.toContain('strict-transport-security')
  })

  it('propagates a malformed API URL instead of shipping a fallback header set', () => {
    // next.config.ts calls securityHeaders() directly, not contentSecurityPolicy(),
    // to fail the build on a bad NEXT_PUBLIC_API_URL. That guarantee only holds
    // if this function itself throws rather than catching internally.
    expect(() => securityHeaders({ apiUrl: 'not a url' })).toThrow(/NEXT_PUBLIC_API_URL/)
  })
})
