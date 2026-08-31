import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";
import { securityHeaders } from "./app/lib/contentSecurityPolicy";
import { version } from "./package.json";

// Keyed on the phase Next passes in, not on NODE_ENV. `next build` only
// defaults NODE_ENV and preserves an inherited one, so a build environment that
// happened to export NODE_ENV=development would otherwise bake the tolerant
// policy - eval, and a hot-reload socket - into a shipped image with nothing to
// signal it. The phase cannot be inherited from a shell.
//
// The config is evaluated once, at load, so a malformed NEXT_PUBLIC_API_URL
// fails the build here rather than shipping a page whose connect-src cannot
// reach the backend.
// The version the footer will show, refused rather than defaulted if the
// manifest did not yield one. `app/lib/version.ts` falls back to `dev` for the
// environments that have no build behind them, and that fallback is a plausible
// string: a build whose injection broke would ship a footer misreporting which
// build a clinician is looking at, and would report it quietly. This is the
// same call `apiOrigin` makes about `NEXT_PUBLIC_API_URL` - a value this file
// cannot get right is a build failure, not a runtime default. It also covers
// the named JSON import: a loader that ever hands back `undefined` stops here.
function appVersion(): string {
  if (typeof version !== "string" || version.trim() === "") {
    throw new Error(
      "package.json has no usable `version`; the footer would misreport the build.",
    );
  }
  return version;
}

export default function config(phase: string): NextConfig {
  const headers = securityHeaders({
    apiUrl: process.env.NEXT_PUBLIC_API_URL,
    development: phase === PHASE_DEVELOPMENT_SERVER,
  }).map(({ key, value }) => ({ key, value }));

  return {
    output: "standalone",
    // The manifest is read here rather than imported by the component that
    // displays it, so the version reaches the bundle as a literal and the
    // dependency list it sits next to does not reach the bundle at all.
    env: {
      NEXT_PUBLIC_APP_VERSION: appVersion(),
    },
    async headers() {
      return [
        {
          source: "/:path*",
          headers,
        },
      ];
    },
  };
}
