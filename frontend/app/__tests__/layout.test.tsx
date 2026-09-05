import { readFileSync } from 'node:fs'
import path from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PrivacyBadge } from '../components/PrivacyBadge'
import { UNSECURED_DEPLOYMENT_VARIABLE } from '../lib/deployment'

// `next/font/google` and the global stylesheet both need the real Next build
// pipeline to resolve; mocked here so the layout can be rendered under vitest
// at all. Neither is what these tests are about.
vi.mock('../globals.css', () => ({}))
vi.mock('next/font/google', () => ({
  Newsreader: () => ({ variable: 'newsreader' }),
  Public_Sans: () => ({ variable: 'public-sans' }),
}))

// Imported after the mocks above, which vitest hoists - but written below them
// so the ordering that matters is visible rather than relying on the hoist.
import RootLayout from '../layout'

const ORIGINAL_VALUE = process.env[UNSECURED_DEPLOYMENT_VARIABLE]

afterEach(() => {
  if (ORIGINAL_VALUE === undefined) delete process.env[UNSECURED_DEPLOYMENT_VARIABLE]
  else process.env[UNSECURED_DEPLOYMENT_VARIABLE] = ORIGINAL_VALUE
})

describe('RootLayout', () => {
  it('shows the unsecured-deployment notice and hides the privacy badge when the variable is on', () => {
    process.env[UNSECURED_DEPLOYMENT_VARIABLE] = 'true'

    render(
      <RootLayout>
        <PrivacyBadge />
      </RootLayout>
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('Reste sur cette machine')).not.toBeInTheDocument()
  })

  it('shows the ordinary interface when the variable is unset', () => {
    delete process.env[UNSECURED_DEPLOYMENT_VARIABLE]

    render(
      <RootLayout>
        <PrivacyBadge />
      </RootLayout>
    )

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Reste sur cette machine')).toBeInTheDocument()
  })

  it('reads the flag through a literal property access, not a computed one', () => {
    // Next only inlines `process.env.NAME` written literally at build time.
    // `process.env[NAME]` is not rewritten and reads undefined in the built
    // server - the banner then never appears in production - while every test
    // above stays green, because Node evaluates both forms identically outside
    // Next's build. That gap is why this is a source check rather than a
    // render assertion: nothing this suite can execute would tell the two
    // forms apart. See the comment above the line in layout.tsx.
    // The comment above the real line spells out the rejected, computed form
    // as documentation, so the check below is scoped to the call that actually
    // reads the flag rather than to the whole file.
    const source = readFileSync(path.resolve(__dirname, '../layout.tsx'), 'utf8')
    const flagRead = source
      .split('\n')
      .find(line => line.includes('unsecuredDeployment(process.env'))

    expect(flagRead).toMatch(new RegExp(`process\\.env\\.${UNSECURED_DEPLOYMENT_VARIABLE}\\b`))
    expect(flagRead).not.toMatch(/process\.env\[/)
  })

  it('still opts out of the build-time prerender', () => {
    // The other half of the same class of bug, and the more consequential one.
    // `force-dynamic` is the only thing keeping this layout out of the
    // prerender; without it `next build` bakes the build container's value -
    // nothing - into the shell, the banner never renders in any deployment,
    // and every test above stays green because vitest renders the component
    // directly and never goes through Next's prerender.
    const source = readFileSync(path.resolve(__dirname, '../layout.tsx'), 'utf8')

    expect(source).toMatch(/export const dynamic = ['"]force-dynamic['"]/)
  })
})
