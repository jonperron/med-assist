import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";
import { securityHeaders } from "./app/lib/contentSecurityPolicy";

// Keyed on the phase Next passes in, not on NODE_ENV. `next build` only
// defaults NODE_ENV and preserves an inherited one, so a build environment that
// happened to export NODE_ENV=development would otherwise bake the tolerant
// policy - eval, and a hot-reload socket - into a shipped image with nothing to
// signal it. The phase cannot be inherited from a shell.
//
// The config is evaluated once, at load, so a malformed NEXT_PUBLIC_API_URL
// fails the build here rather than shipping a page whose connect-src cannot
// reach the backend.
export default function config(phase: string): NextConfig {
  const headers = securityHeaders({
    apiUrl: process.env.NEXT_PUBLIC_API_URL,
    development: phase === PHASE_DEVELOPMENT_SERVER,
  }).map(({ key, value }) => ({ key, value }));

  return {
    output: "standalone",
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
