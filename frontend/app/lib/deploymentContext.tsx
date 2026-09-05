'use client'

import { createContext, useContext } from 'react'

/**
 * Carries the unsecured-deployment flag from the server layout into the page.
 *
 * The flag is read at request time in a server component, and the screen that
 * has to react to it is a client one. A context is the seam between them: the
 * layout provides the value it read, and anything below can ask for it without
 * the flag becoming a `NEXT_PUBLIC_` build-time constant - which is the whole
 * point of reading it on the server. See `deployment.ts`.
 *
 * It defaults to false so a component rendered outside the provider - a test
 * for something else, most often - gets the ordinary local interface rather
 * than a warning it did not ask for. The provider is in the root layout, so
 * every real render has a value.
 */
const UnsecuredDeploymentContext = createContext(false)

export function UnsecuredDeploymentProvider({
  unsecured,
  children,
}: {
  unsecured: boolean
  children: React.ReactNode
}) {
  return (
    <UnsecuredDeploymentContext.Provider value={unsecured}>
      {children}
    </UnsecuredDeploymentContext.Provider>
  )
}

/** Whether this deployment is open to anyone who can reach it. */
export function useUnsecuredDeployment(): boolean {
  return useContext(UnsecuredDeploymentContext)
}
