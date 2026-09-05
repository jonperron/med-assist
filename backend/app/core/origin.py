"""
The gate that refuses a request driven by a site the deployment does not serve.

CORS is not a control on the server. `CORSMiddleware` decides which origins may
*read* an answer, and a browser enforces that by withholding the response from
the page that asked. The request itself is sent, and this API acts on it:
another site can drive `POST /api/analyze` from a visitor's browser, and the
documents are parsed, the model is invoked, and the deployment pays for the
work. The attacker never sees the summary - CORS does hold that line, and the
service stores nothing - but it decided what this deployment analysed. Where an
authenticating proxy sits in front, that is sharper still: the visitor's cached
credentials are ambient, so the proxy accepts the forged request and forwards
it exactly as it would forward one the visitor typed the address of. Nothing
behind the proxy can see the difference, because as far as the backend is
concerned the request came through the front door.

This gate closes that. The `Origin` header is compared against the same list
`CORSMiddleware` was configured with, on the server, before the body is read.
A request from a site that is not on the list is refused with 403 whether or not
a browser would have let the page read the answer.

Two limits, stated rather than implied:

**An `Origin` header is not proof of anything on its own.** A browser sets it
and a page cannot forge it, which is the whole basis of this control; a client
that is not a browser writes whatever it likes there. So this gate constrains
*browsers* - which is exactly the CSRF case it exists for - and constrains a
scripted caller not at all. Nothing on this API does: there is no credential,
and a scripted caller that can reach the port can already submit documents.

**A request carrying no `Origin` at all is allowed through.** That is not a
loophole left open by accident: the documented deployment shape puts a proxy in
front, and a proxy forwarding a server-side call sends no `Origin`. Refusing
those would refuse the healthcheck, every `curl`, and the proxy itself. A
browser, meanwhile, always sends `Origin` on the methods these routes accept -
the Fetch standard requires it on everything that is not a GET or a HEAD - so
the case this gate exists to refuse cannot arrive without one. `Sec-Fetch-Site`
is consulted for the remainder: when a request carries no `Origin` but does
carry that header, it came from a browser that chose not to send one, and the
browser's own account of where it came from is used instead.
"""

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Scope

from app.core.gate import CoveredRouteGate

# The variable the allow-list is read from. It is `CORSConfiguration`'s, not one
# of this module's own: a second list would let the advisory control and the
# enforced one drift, and the failure that produces is the worst of both - a
# browser told it may call an endpoint that then refuses it, or an endpoint
# enforcing a list nobody updated when the frontend moved.
ORIGIN_VARIABLE = "CORS_ALLOWED_ORIGINS"

# The one refusal this module sends. Fixed, and identical whether the origin was
# unknown or the browser reported a cross-site navigation: which of those it was
# is information the caller has not earned.
FORBIDDEN = "Forbidden"

# What the log line says. Never the origin itself - it is attacker-controlled
# text, and writing it verbatim into a log file is how a log viewer ends up
# rendering someone else's content.
UNKNOWN_ORIGIN = "the origin is not one this deployment serves"

# `Sec-Fetch-Site` values that describe a request this deployment's own pages
# started, or that no page started at all. `none` is a direct navigation or a
# bookmark. A browser sets this header itself and a page cannot: it is a
# forbidden header name, so script has no way to write it. That is what makes
# it safe to *accept* on, and it is the reason the one-domain proxy shape in
# `deploy/` works without the operator listing their own origin.
OWN_SITES = (b"same-origin", b"none")

# There is deliberately no list of *foreign* `Sec-Fetch-Site` values. Anything
# that is not in `OWN_SITES` and arrives without an `Origin` is refused, so an
# empty, malformed or later-standardised value fails closed rather than being
# admitted by a deny-list that had not heard of it.
#
# This branch decides nothing today: both analysis routes are POST, and a
# browser always sends `Origin` on a POST. It would begin to matter the day a
# GET route is added under `/api` - and note that a browser old enough not to
# send `Sec-Fetch-Site` at all would then reach the no-header case below and be
# let through, which is the limit of what a header-based check can promise.


def header(scope: Scope, name: bytes) -> bytes | None:
    """
    Return the first value of a header, or None when it is absent.

    The first only. A request carrying two `Origin` headers is malformed, and
    taking the first is what every proxy in front of this process will also have
    done; trying each in turn would let a caller append an accepted value to a
    request whose real origin was refused.

    :param scope: The ASGI connection scope.
    :param name: The lowercase header name, as bytes.
    :return: The value with surrounding whitespace removed, or None.
    """
    for raw_name, value in scope.get("headers", []):
        # Lowercased rather than compared to a lowercase literal. ASGI servers
        # are required to normalise header names and uvicorn does, but a
        # security control should not be the thing that depends on it.
        if raw_name.lower() == name:
            return value.strip()
    return None


class RequireKnownOrigin(CoveredRouteGate):
    """
    Refuse a request to the analysis routes that another site drove.

    Mounted always, and it is the only gate in front of the analysis routes - the
    credential that used to sit alongside it is gone. **The allow-list is not
    private, and nothing here tries to make it so.** It never fully was:
    `CORSMiddleware` sits outside this gate - it has to, because it answers
    preflights itself - and it answers an `OPTIONS` preflight naming an origin
    with 200 or 400 according to whether that origin is allowed. So the list was
    always confirmable, one guess at a time, by anyone who can reach the port.

    While the credential was mounted outside this gate, the analysis routes at
    least did not answer the same question a second time: an anonymous caller
    saw 401 whatever origin it claimed. That is gone with the credential, and
    the routes are now the second oracle the ordering used to prevent - a caller
    can tell an allowed origin from a refused one by 403 against 422. Nothing is
    lost that the preflight was not already giving away, and `deploy/README.md`
    says to treat `CORS_ALLOWED_ORIGINS` as public.

    The comparison is byte-for-byte against origins normalised at startup by
    `normalise_origin`, which is what makes it safe to be exact. A browser sends
    `https://host` for a default port and lowercases the scheme and host, and
    that function rewrites the configured entries into the same form - so an
    operator who wrote `https://Host:443/` gets a list this gate matches rather
    than one that silently allows nothing.
    """

    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...]) -> None:
        super().__init__(app)
        # Held as bytes because that is what the header is, and comparing bytes
        # avoids decoding attacker-controlled input on every request.
        self.allowed = tuple(origin.encode("utf-8") for origin in allowed_origins)

    def accepts(self, scope: Scope) -> bool:
        """
        Whether the request came from somewhere this deployment serves.

        :param scope: The ASGI connection scope.
        :return: True when the origin is on the list, or when the request
            carries no browser account of where it came from at all.
        """
        site = header(scope, b"sec-fetch-site")
        if site is not None and site.lower() in OWN_SITES:
            # The browser says this deployment's own page made the request, and
            # a page cannot forge that header. Accepted before the allow-list is
            # consulted so that the recommended shape - one domain serving the
            # interface and `/api` alike - works without the operator listing
            # their own origin. Without this, a same-origin deployment that
            # never needed CORS would refuse every analysis with a 403 whose
            # body says nothing about which list it was compared against.
            return True

        origin = header(scope, b"origin")
        if origin is not None:
            # `null` is what a browser sends from a sandboxed iframe, a
            # `data:` document or a redirected cross-origin request. It is not
            # an origin any deployment can serve, and `normalise_origin`
            # refuses it as configuration, so it falls out here as unknown.
            return origin in self.allowed

        if site is not None:
            # No `Origin`, and the browser has already said the request did not
            # come from this deployment's own pages. Refused rather than tested
            # against a list of foreign values: a deny-list here would admit
            # anything unrecognised - an empty header, a malformed one, a value
            # added to the standard later - and it is the only comparison in
            # this module that could fail open. `same-site` is refused with
            # `cross-site` because a sibling subdomain is still a different
            # origin, and one that is meant to call this API belongs in the
            # allow-list by name.
            return False

        # No `Origin`, no `Sec-Fetch-Site`: not a browser request. The proxy,
        # the healthcheck and every scripted caller land here, and nothing on
        # this API gates them - there is no credential. See the module
        # docstring.
        return True

    def refusal(self) -> JSONResponse:
        """
        The refusal, in the envelope every other refusal on this API uses.

        403 rather than 401: the caller's identity is not in question and
        presenting a credential would not change the answer, so there is no
        `WWW-Authenticate` header to send. The frontend already reads 401 and
        403 as the same unretryable condition.
        """
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": {"message": FORBIDDEN}},
        )

    def refusal_reason(self) -> str:
        return UNKNOWN_ORIGIN
