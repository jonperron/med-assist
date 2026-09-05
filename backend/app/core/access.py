"""
The shared credential required in front of the analysis routes.

This service has never authenticated anyone. That was defensible while the only
way to reach it was `docker compose up` on the machine in front of you; it is
not defensible once a proxy can put port 8000 on a public name. CORS does not
help - it is a browser-side control, and a client that is not a browser ignores
it entirely.

What this adds is one shared secret, read from `API_ACCESS_TOKEN`, checked on
the analysis routes and nowhere else. Three things about it are deliberate, and
the second and third are the honest limits of it:

**It is required, and the process refuses to start without it.** This gate was
introduced as off-by-default so that no existing deployment broke on an upgrade.
That default was the whole security posture of every deployment that did not
read the release notes: an unconfigured service answered anyone who could reach
the port while looking, from the outside, exactly like a configured one. There
is no longer an unconfigured mode to be in by accident. An operator who mistypes
the variable name now gets a container that stops with a message naming the
variable, which is the loudest failure available and far cheaper than the quiet
one it replaces.

The cost is real and is not hidden: `docker compose up` with no `.env` no longer
starts. That is the point - the alternative is a service that starts and is
open - but it makes first-run setup a step longer, and `.env.example` and
`deploy/README.md` carry the one command that generates a value.

**It is not a password for a person.** One secret shared by every caller
identifies nobody, cannot be revoked for one client, and appears in whatever
holds the environment of whatever calls the API. It answers "is this caller
someone the operator set up" and no other question. Authenticating a *human*
belongs in a proxy in front of this process, which can also then supply this
credential on the way through.

**The shipped browser frontend cannot use it.** It talks to this API directly
from the page, so any credential it could send is a credential every visitor can
read - out of the bundle, out of the network tab, out of a response the frontend
server would have to hand to anyone who asked for it. There is no arrangement
where a public single-page application holds a secret. Since the credential is
required, the shipped interface is therefore off in *every* deployment that does
not put an authenticating proxy in front to add the header - which makes that
proxy the way to get a working interface, not an optional hardening step.

The check is ASGI middleware rather than a route dependency for one reason that
matters: FastAPI parses a multipart body before it solves any dependency, so a
dependency would refuse the caller only after the server had already spooled up
to the whole request ceiling into `TMPDIR`. Here the refusal is decided from the
request headers and nothing is read.
"""

import hmac

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp, Scope

from app.core.gate import PROTECTED_PREFIX, CoveredRouteGate

# The variable the credential is read from. Named here so the startup log and
# the refusal message cannot drift from what an operator has to set.
ACCESS_TOKEN_VARIABLE = "API_ACCESS_TOKEN"

# `PROTECTED_PREFIX` is re-exported rather than defined here. Both gates cover
# the same prefix by construction, so it is owned by `gate.py` - two copies
# could disagree, and the one that lost would be a control silently narrower
# than the routes it guards.
__all__ = [
    "ACCESS_TOKEN_VARIABLE",
    "BEARER_SCHEME",
    "MINIMUM_TOKEN_LENGTH",
    "PROTECTED_PREFIX",
    "UNAUTHORIZED",
    "AccessTokenConfiguration",
    "AccessTokenError",
    "RequireAccessToken",
    "configured_access_token",
]

# The scheme the credential is presented under. Bearer rather than a header of
# our own so that every proxy, client library and log scrubber already knows to
# treat the value as a secret.
BEARER = b"bearer"

# What the OpenAPI document calls that scheme. The gate is middleware, so
# FastAPI cannot infer a security requirement from it the way it would from a
# route dependency; the name is declared here, referenced by the analysis routes
# and defined as a component by `create_app`, so the three cannot drift.
BEARER_SCHEME = "bearerCredential"

# The one refusal this module sends. Fixed, and identical whether the header
# was absent, malformed, or held the wrong value: which of those it was is
# information the caller has not earned.
UNAUTHORIZED = "Unauthorized"

# Shortest credential accepted. A shared secret is the only thing between the
# analysis routes and everyone who can reach the port, and the caller it keeps
# out is the one who can retry indefinitely, so it has to be generated rather
# than chosen. 32 characters is `secrets.token_urlsafe(24)`; the message below
# suggests more.
MINIMUM_TOKEN_LENGTH = 32

# What the log line says about a refusal. Never the header, in any form.
NO_CREDENTIAL = "no valid credential was presented"


class AccessTokenError(RuntimeError):
    """
    Raised at startup when `API_ACCESS_TOKEN` is set to something unusable.

    A `RuntimeError` rather than a `ValueError` for the same reason
    `CORSOriginError` is one, and more sharply here: pydantic turns a
    `ValueError` raised in a validator into a `ValidationError` that quotes the
    input it rejected, and the input here is the secret itself. Nothing in this
    module ever puts the value in a message, an exception or a log line - not
    truncated, not hashed, not its length.
    """


class AccessTokenConfiguration(BaseSettings):
    """
    The credential the analysis routes require.

    Typed as a plain string with a default so that pydantic itself can never
    fail on it: every validation failure it could raise would carry the secret
    into the traceback. The one rule that does apply - a minimum length - is
    checked by `configured_access_token` afterwards, where the message can be
    written by hand.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Without this the alias alone would make `AccessTokenConfiguration(
        # token=...)` drop the argument as an extra field and hand back the
        # default - a gate that silently configures itself open.
        populate_by_name=True,
    )

    token: str = Field(
        default="",
        alias=ACCESS_TOKEN_VARIABLE,
        description=(
            "Shared credential required on the analysis routes, presented as "
            "an Authorization: Bearer header. Unset or blank stops the process "
            "at startup: there is no mode in which these routes answer a caller "
            "that presented nothing."
        ),
    )

    @field_validator("token", mode="after")
    @classmethod
    def without_surrounding_whitespace(cls, raw: str) -> str:
        """
        Trim the value, so a blank variable is indistinguishable from an unset one.

        A Compose passthrough with nothing behind it arrives as the empty
        string, and a value wrapped over two lines in a `.env` arrives with a
        newline; neither is a credential a caller could present.

        This validator only ever returns - it cannot raise, and nothing here
        may. A `ValueError` out of a pydantic validator becomes a
        `ValidationError` that quotes the input it rejected, and the input here
        is the secret. The one rule that can fail lives in
        `configured_access_token`, where the message is written by hand.
        """
        return raw.strip()


def generate_it_with() -> str:
    """The one command both refusals below end on, so they cannot disagree."""
    return 'python -c "import secrets; print(secrets.token_urlsafe(32))"'


def configured_access_token() -> str:
    """
    Read the credential, or stop the process.

    Whitespace is stripped and a blank value reads as unset: a variable passed
    through an empty Compose default is a deployment that did not configure a
    credential, not one that configured the empty string. Both are refused
    identically, and neither starts a server.

    Refusing here rather than defaulting to an open service is the trade this
    module's docstring describes: a deployment that has not been configured
    fails loudly at startup instead of quietly answering everyone.

    :return: The credential.
    :raises AccessTokenError: If no value is set, or the value is too short to
        be a secret.
    """
    token = AccessTokenConfiguration().token
    if not token:
        raise AccessTokenError(
            f"{ACCESS_TOKEN_VARIABLE} is not set. The analysis routes ingest "
            "clinical documents and this credential is what keeps them from "
            "answering anyone who can reach the port, so there is no default "
            "and no unconfigured mode. Generate one and put it in the "
            f"environment: {generate_it_with()}. The browser interface in this "
            "stack cannot present it - see deploy/README.md for the proxy that "
            "can."
        )
    if len(token) < MINIMUM_TOKEN_LENGTH:
        raise AccessTokenError(
            f"{ACCESS_TOKEN_VARIABLE} must be at least {MINIMUM_TOKEN_LENGTH} "
            "characters. It is the only thing between the analysis routes and "
            "everyone who can reach the port, so generate it rather than "
            f"choosing it: {generate_it_with()}. The value is left out of this "
            "message because it is a secret."
        )
    return token


def unauthorized() -> JSONResponse:
    """
    The refusal, in the envelope every other refusal on this API uses.

    `WWW-Authenticate` is what makes the 401 a correct one rather than a 403
    spelled differently, and it names the scheme without saying anything about
    the credential. There is no `realm`: it would be either a deployment's own
    hostname or a fixed string, and the first is configuration this refusal has
    no business naming.
    """
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": {"message": UNAUTHORIZED}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def presented_credential(scope: Scope) -> bytes | None:
    """
    Return the credential the request presented, if it presented one.

    The first `Authorization` header only. A request carrying two is malformed
    under RFC 9110 and taking the first is what every server in front of this
    one will also have done; trying each in turn would let a caller append
    guesses to a request that already has a valid header.

    :param scope: The ASGI connection scope.
    :return: The bytes after the scheme, or None if there is no bearer header.
    """
    for name, value in scope.get("headers", []):
        if name.lower() != b"authorization":
            continue
        scheme, separator, credential = value.partition(b" ")
        if not separator or scheme.lower() != BEARER:
            return None
        return credential.strip()
    return None


class RequireAccessToken(CoveredRouteGate):
    """
    Refuse a request to the analysis routes that does not carry the credential.

    Always mounted: `configured_access_token` stops the process rather than
    return nothing, so there is no build of the application in which this gate
    is absent.

    Two things about its placement are deliberate:

    - **Everything outside `/api` is open, not only the health endpoints.** The
      gate is a prefix, so `/healthz`, `/readyz`, `/`, FastAPI's `/docs`,
      `/redoc` and `/openapi.json`, and the development-only `/mock_summary`
      all answer without a credential. The two health endpoints are the
      deliberate part: the container healthcheck calls readiness from inside
      the container, where it could hold the credential and does not need to,
      and the interface's availability poll calls it from a browser, where it
      could not hold one at all. What they disclose is whether a process is up
      and whether weights are in memory - no configuration, no document. The
      schema endpoints are the incidental part, and a deployment that does not
      want its API described to strangers has to keep them off the proxy;
      `deploy/caddy/Caddyfile.example` routes only `/api`, `/healthz` and
      `/readyz` to this service, so they are not reachable there. This is
      stated at length because the set is wider than "the health endpoints",
      and because a future router mounted outside `/api` would be ungated with
      nothing failing - `test_access_token.py` pins the current set so that
      addition breaks a test.
    - **It is mounted outside `RequireKnownOrigin`**, so it runs first. A caller
      that presents nothing is refused with 401 whatever origin it claimed, so
      the analysis routes do not report on the origin allow-list to an anonymous
      caller watching a 403 turn into a 401. That is narrower than "the list is
      private": the CORS preflight, which is answered outside both gates and
      without a credential, already confirms a guessed origin. See
      `RequireKnownOrigin`.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        # Held as bytes because that is what the header is, and comparing bytes
        # avoids a decode of attacker-controlled input on every request.
        self.expected = token.encode("utf-8")

    def accepts(self, scope: Scope) -> bool:
        """
        Whether the request carries the configured credential.

        `compare_digest` rather than `==` so that the time taken does not
        describe how much of a guess was right. It is not a complete defence -
        the length of the presented value is still observable - but the
        credential is long and random, which is what makes the remaining signal
        useless.

        :param scope: The ASGI connection scope.
        :return: True when the presented credential is the configured one.
        """
        credential = presented_credential(scope)
        if credential is None:
            return False
        return hmac.compare_digest(credential, self.expected)

    def refusal(self) -> JSONResponse:
        return unauthorized()

    def refusal_reason(self) -> str:
        return NO_CREDENTIAL
