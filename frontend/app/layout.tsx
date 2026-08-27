import type { Metadata } from 'next'
import { Newsreader, Public_Sans } from 'next/font/google'
import './globals.css'

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
  return (
    <html lang="fr">
      <body className={`${newsreader.variable} ${publicSans.variable} antialiased`}>
        {children}
      </body>
    </html>
  )
}
