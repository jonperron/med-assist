import type { Metadata } from 'next'
import { Newsreader, Public_Sans } from 'next/font/google'
import { UnsecuredDeploymentNotice } from './components/UnsecuredDeploymentNotice'
import './globals.css'
import { unsecuredDeployment } from './lib/deployment'
import { UnsecuredDeploymentProvider } from './lib/deploymentContext'

// Rendered per request rather than prerendered at build. The whole point of
// reading the warning flag from the environment instead of from a
// `NEXT_PUBLIC_` constant is that an operator can turn it on with a restart and
// no rebuild - and a statically prerendered layout would bake whatever the
// value was in the build container, which is nothing. The cost is one server
// render per page load of an application that is a single interactive screen.
export const dynamic = 'force-dynamic'

// Newsreader carries the headings and section titles, Public Sans everything
// else. Both are loaded through next/font so the faces are self-hosted: a
// clinician's machine never reaches a font CDN to render a patient summary.
const newsreader = Newsreader({
  variable: '--font-newsreader',
  subsets: ['latin'],
  weight: ['300', '400', '500'],
})

const publicSans = Public_Sans({
  variable: '--font-public-sans',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
})

export const metadata: Metadata = {
  title: 'Med-Assist',
  description: "Résumé clinique de plusieurs documents d'un même patient.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  // Written as a literal member access rather than
  // `process.env[UNSECURED_DEPLOYMENT_VARIABLE]`, and that is not a style
  // choice: Next rewrites `process.env.FOO` at build time and a computed key is
  // not rewritten, so the dynamic form read undefined here and the banner never
  // appeared however the variable was set. The constant still names the
  // variable for the tests and the documentation; this line is the one place
  // that has to spell it out, and `deployment.test.ts` covers the parsing.
  const unsecured = unsecuredDeployment(process.env.UNSECURED_DEPLOYMENT)

  return (
    <html lang="fr">
      <body className={`${newsreader.variable} ${publicSans.variable} antialiased`}>
        {unsecured && <UnsecuredDeploymentNotice />}
        <UnsecuredDeploymentProvider unsecured={unsecured}>
          {children}
        </UnsecuredDeploymentProvider>
      </body>
    </html>
  )
}
