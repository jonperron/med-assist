---
type: decision
title: 2026-08-31 - The footer states the version, the address and what is kept
description: Both screens carry a footer with the build version injected from package.json, a link to the public issue tracker, and the retention claim spelled out; an existing test that banned the word "serveur" on the page was narrowed to ban controls rather than prose.
tags: [frontend, privacy, ui]
---

# 2026-08-31 - The footer states the version, the address and what is kept

## What was decided

`frontend/app/components/AppFooter.tsx` sits below `main` on both screens - the
upload screen in `app/page.tsx` and `SummaryView` - and carries three things:
the build version, a link to the public issue tracker, and one sentence on what
becomes of a submitted document.

**That a version belongs on screen at all.** This interface withholds mechanism
on purpose: sources are counted rather than named, entity offsets stay on the
server, and there are no confidence scores, model names, timings or ids. A build
number is mechanism, so it needs the exception argued rather than assumed.

It earns the exception because it is the only piece of mechanism here that says
nothing about the reading. A confidence score, a model name or a timing invites
the clinician to weigh the summary differently, and this application has decided
they should not be given that lever, because the summary is assembled by fixed
rules and any such number would be an invention. A version says which software
drew the screen. It changes nothing about how to read the summary, and it is the
first thing a maintainer asks for when something is wrong - which is why it sits
beside the issue link rather than anywhere else, and why both are hidden in
print. The test of the rule is whether a clinician could act differently on the
value; for a version, they could not.

**The version.** `package.json` stays the single source of truth for the number.
`next.config.ts` reads the manifest at build time and injects it through Next's
`env` option, so `process.env.NEXT_PUBLIC_APP_VERSION` is replaced by a string
literal in the bundle. `app/lib/version.ts` reads that variable and falls back
to `dev`. The manifest is deliberately not imported by the component: an
`import` of `package.json` from client code puts the whole file - every
dependency and every version range - into the bundle to read one field, and
neither Webpack nor Turbopack guarantees tree-shaking a JSON module down to a
property. The built output was checked: `0.1.0` appears as a literal and no
dependency name from the manifest appears in any chunk.

`next.config.ts` throws if the manifest yields no usable version rather than
letting the fallback cover for it. `dev` is a plausible string: a build whose
injection broke would ship a footer misreporting which build a clinician is
looking at, and would report it quietly. This is the same call `apiOrigin`
already makes about `NEXT_PUBLIC_API_URL` - a value the config cannot get right
is a build failure, not a runtime default - and it also covers the named JSON
import, since a loader that ever returns `undefined` stops the build instead of
shipping `vdev`.

`vitest.config.ts` defines the same variable from the same manifest, so
`AppFooter.test.tsx` asserts against `version` rather than a hard-coded string
and a release bump does not have to be made in two places. The fallback exists
for environments with no build behind them, and a test asserts the footer is not
showing it.

**The address.** `https://github.com/jonperron/med-assist/issues`, opened with
`target="_blank"` and `rel="noopener noreferrer"`. This is the only off-origin
navigation the interface offers. The CSP does not govern it - `connect-src`
covers fetches, not a user clicking a link, and `navigate-to` ships in no
browser - so what protects the clinician here is that the destination is a
public repository holding no patient data, and that the footer asks them to
report a problem rather than to attach the document that caused it.

**What is kept.** "Aucun document n'est enregistré sur le serveur. Les fichiers
ne vivent que le temps de la requête, dans un stockage temporaire effacé avec
la réponse : pas de base de données, rien à supprimer ensuite."

This is the privacy badge's claim spelled out. The badge answers where the
documents go; the footer answers what is left afterwards. The wording says
"stockage temporaire" rather than "rien n'est écrit sur disque", because the
latter would be false: the HTTP server spools a multipart part above 1 MB, which
`docker-compose.yml` puts on a `tmpfs`. A footer is the wrong place to overstate
a guarantee, and two tests pin it - one on the phrase, one refusing any absolute
claim about erasure anywhere on the page.

The distinction matters more than it looks, because only one half of the
sentence is true everywhere. The spool is an unnamed inode created by
`tempfile`: it is unlinked at creation, so "effacé avec la réponse" holds on any
filesystem, even after a hard kill. What is deployment-dependent is whether
erasure is *unrecoverable* - freed blocks on a disk-backed `/tmp` are not
overwritten. `docker-compose.yml` mounts a RAM-backed `/tmp` and sets `TMPDIR`;
the backend Dockerfile sets neither, and a bare `uvicorn` run writes the spool to
a real filesystem, as `backend/README.md` already says. The footer's sentence
claims only what holds in every case, so it stays as written; what the operator
has to supply is recorded here and in `frontend/README.md` rather than hedged on
screen, because a caveat is not what a footer is the right size for.

The footer is `data-print="hide"`. A summary going into a patient file is about
the patient; a version number and an issue tracker are about this software.

It is mounted on the two screens a clinician works from - the upload screen and
`SummaryView` - and not on `app/error.tsx` or `app/global-error.tsx`. The error
screen is a single centred card with no chrome at all, and it already carries
the claim in the form that screen needs: "Rien n'a été conservé."

**One existing test was changed.** `page.test.tsx` had an assertion, under
"offers no storage, retention or masking controls", that no text matching
`/serveur|supprim|masqu/i` appeared anywhere on the page. Its comment says the
clinician is asked for documents and not for a data-handling policy, so the
banned words were standing in for banned widgets. A static sentence stating what
the service does is not the thing that test was defending against, and reading
it as one would have made the interface unable to answer its most likely
question. The assertion was narrowed to what it means: no checkbox, no radio, no
select, and no button whose label offers a choice about retention.

## The alternative that was rejected

Three were.

**Putting the footer in `app/layout.tsx`.** It would have appeared once instead
of twice. Rejected because both screens are `min-h-screen` flex columns, so a
footer outside them sits below the fold and has to be scrolled to on a screen
that otherwise never scrolls. Mounting it inside each column, with `main`
holding `grow`, puts it at the bottom of the viewport when the content is short
and after the content when it is long. Two call sites is the price, and both are
covered by a test that fails if either is dropped.

**Reading the version by importing `package.json` in the component.** Two lines
instead of six, and no build-time wiring. Rejected for the bundle cost described
above: the dependency list of a clinical tool is a small piece of reconnaissance
to hand out for free, and the tree-shaking that would avoid it is a bundler
detail nothing in this repository pins.

**Stating the policy more strongly.** "Vos documents ne quittent jamais cette
machine" was considered and dropped: that is the badge's claim, it is already on
screen, and the boundary the CSP actually enforces is "only the configured API
origin", not "only this machine" - an operator can point `NEXT_PUBLIC_API_URL`
at a public host. Repeating a stronger version of a claim in a second place
would have put the interface's two privacy statements out of step with each
other.

## What it costs

- The version is now a third thing that has to be correct at build time,
  alongside the fetch URL and the CSP origin. The build gate closes the loud
  failure - a missing or empty version stops the build - but not the quiet one:
  `next.config.ts` is the only config in this frontend with no test behind it.
  The CSP was deliberately extracted into `contentSecurityPolicy.ts` so it could
  be unit-tested, and the `env` block was not given the same treatment, so
  `npm run build` is the only thing standing between a broken injection and a
  shipped footer. The vitest `define` mirrors the config rather than sharing
  code with it, and the two could drift without the suite noticing: what is
  tested is that the mechanism works, not that a release artefact carries a
  given number.
- The version resolves to a public tag. Refusing to bundle the manifest keeps
  the dependency set out of the page, but this repository is public and released
  under tags, so a version string in the footer reaches a published
  `package-lock.json` and `uv.lock` - the same reconnaissance by a slower route.
  It costs nothing today, because the application is unauthenticated and
  local-first and anyone who can read the footer can already read the whole
  interface. It would start to cost something if the frontend were ever exposed
  beyond a trusted network, at which point the number should become a build
  identifier that does not resolve to a tag.
- The issue URL is a constant in `version.ts`, not derived from the manifest.
  `package.json` has no `repository` or `bugs` field, so nothing cross-checks the
  address and nothing fails if the repository moves. The manifest is the single
  source of truth for the number, not for the identity beside it.
- `package.json` is now imported by `next.config.ts` and by `vitest.config.ts`,
  which is the manifest becoming a source file. It works today because
  `resolveJsonModule` is on and both configs are transpiled to CommonJS; a move
  to native ESM config loading would need import attributes. The vitest warning
  about `configLoader: 'native'` already visible in the test output is the same
  change arriving, and this makes one more file that will have to move with it.
- The privacy claim is now written in two places in the interface - the badge
  and the footer - plus the README and this wiki. They agree today. Nothing
  enforces that they keep agreeing, and the footer is the one a clinician reads
  most carefully because it is prose rather than a chip.
- An off-origin link on a clinical screen is a new affordance. It is guarded by
  `noopener`, and `Referrer-Policy: no-referrer` keeps the page address out of
  the request, but a clinician who clicks it mid-analysis leaves an interface
  whose entire state is in memory. Nothing is lost - the tab stays open behind
  the new one - but the footer is deliberately quiet: small text, no icon, no
  button.
- The `page.test.tsx` guard survived, but as two assertions instead of one. The
  vocabulary ban is scoped to `main`, so the footer is exempt by construction
  rather than by the assertion being deleted; a second one refuses any absolute
  claim about erasure across the whole page, footer included. The first version
  of this change replaced the ban with a scan of button and link labels, which
  was close to vacuous - the upload screen has one button and one link on first
  render - and would have let a future false promise through as prose.
- The footer's privacy sentence is set in `ink-soft` rather than the `ink-muted`
  that chrome of this size takes elsewhere in the interface. Muted on white is
  3.6:1, below the 4.5:1 floor for text this size. That makes the footer very
  slightly louder than a footer wants to be, which is the right trade for the
  one sentence on screen that must not be the hard one to read - but it also
  means `ink-muted` is now used at small sizes in places this entry does not
  fix (`page.tsx`, the patient line in `SummaryView`). Those are a separate
  change.
