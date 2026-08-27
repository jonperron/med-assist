'use client'

/**
 * The boundary below the boundary.
 *
 * `app/error.tsx` cannot catch a throw in the root layout, or one raised
 * inside itself; without this those reach Next's built-in error page. It
 * carries its own `html` and `body` because it replaces the root layout it is
 * standing in for, and it says as little as the card in `error.tsx` does.
 */
export default function RootBoundary({ reset }: { reset: () => void }) {
  return (
    <html lang="fr">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif' }}>
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            maxWidth: '520px',
            margin: '15vh auto',
            padding: '24px 28px',
          }}
        >
          <strong style={{ fontSize: '16px' }}>Med-Assist n&apos;a pas pu s&apos;afficher</strong>
          <span style={{ fontSize: '14px', lineHeight: 1.6 }}>
            Rien n&apos;a été conservé. Rechargez la page pour reprendre depuis vos
            documents.
          </span>
          <button type="button" onClick={reset} style={{ width: 'fit-content', padding: '10px 18px' }}>
            Recommencer
          </button>
        </div>
      </body>
    </html>
  )
}
