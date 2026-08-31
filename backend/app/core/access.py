"""
The optional shared credential in front of the analysis routes.

This service has never authenticated anyone. That was defensible while the only
way to reach it was `docker compose up` on the machine in front of you; it is
not defensible once a proxy can put port 8000 on a public name. CORS does not
help - it is a browser-side control, and a client that is not a browser ignores
it entirely.

What this adds is one shared secret, read from `API_ACCESS_TOKEN`, checked on
the analysis routes and nowhere else. Three things about it are deliberate, and
the second and third are the honest limits of it:

**It is off unless configured.** An unset variable leaves the application
exactly as it was, so no existing deployment breaks on an upgrade and the
default stays the local one. The trade is that an operator who mistypes the
variable name gets a service that is open and looks configured, which is why
`create_app` logs which of the two modes it started in.

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
where a public single-page application holds a secret. Configuring a token
therefore turns the shipped interface off, and the deployment that wants both
puts an authenticating proxy in front and has *it* add the header.

The check is ASGI middleware rather than a route dependency for one reason that
matters: FastAPI parses a multipart body before it solves any dependency, so a
dependency would refuse the caller only after the server had already spooled up
to the whole request ceiling into `TMPDIR`. Here the refusal is decided from the
request headers and nothing is read.
"""

import hmac
import logging

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# The variable the credential is read from. Named here so the startup log and
# the refusal message cannot drift from what an operator has to set.
ACCESS_TOKEN_VARIABLE = "API_ACCESS_TOKEN"

# Where the analysis routes are mounted. The gate covers this prefix and
# nothing else: liveness, readiness and the root are deliberately open, see
# `covers`.
PROTECTED_PREFIX = "/api"

# The scheme the credential is presented under. Bearer rather than a header of
# our own so that every proxy, client library and log scrubber already knows to
# treat the value as a secret.
BEARER = b"bearer"

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
    The credential the analysis routes require, if a deployment sets one.

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
            "an Authorization: Bearer header. Unset or blank leaves the routes "
            "open to anyone who can reach the port."
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


def configured_access_token() -> str:
    """
    Read the credential, or refuse a value that would not be one.

    Whitespace is stripped and a blank value reads as unset: a variable
    passed through an empty Compose default is a deployment that did not
    configure a credential, not one that configured the empty string.

    :return: The credential, or an empty string when none is configured.
    :raises AccessTokenError: If a value is set but is too short to be a secret.
    """
    token = AccessTokenConfiguration().token
    if token and len(token) < MINIMUM_TOKEN_LENGTH:
        raise AccessTokenError(
            f"{ACCESS_TOKEN_VARIABLE} must be at least {MINIMUM_TOKEN_LENGTH} "
            "characters. It is the only thing between the analysis routes and "
            "everyone who can reach the port, so generate it rather than "
            'choosing it: python -c "import secrets; '
            'print(secrets.token_urlsafe(32))". The value is left out of this '
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


class RequireAccessToken:
    """
    Refuse a request to the analysis routes that does not carry the credential.

    Mounted only when one is configured, so an unconfigured deployment does not
    pay for a check that would always pass.

    Three paths through it are deliberate:

    - `/healthz` and `/readyz` are never covered. The container healthcheck
      calls readiness from inside the container, where it could hold the
      credential and does not need to; the frontend's availability poll calls it
      from a browser, where it could not hold one at all. Between them that
      settles it. What the two endpoints disclose is whether a process is up and
      whether weights are in memory - no configuration, no document, nothing
      that names a patient - so gating them would cost the interface its "the
      service is starting" notice and buy nothing.
    - A CORS preflight never reaches here. `CORSMiddleware` is mounted outside
      this one and answers `OPTIONS` itself, which it has to: a browser sends no
      `Authorization` on a preflight, so a gate that saw one would refuse the
      request that exists to ask whether the real one may be sent.
    - The refusal is written straight to `send`, like the size ceiling's 413.
      That is why CORS belongs outside this middleware and caching control
      outside that - the 401 picks up the allow-origin header on the way out,
      and `no-store` with it.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        # Held as bytes because that is what the header is, and comparing bytes
        # avoids a decode of attacker-controlled input on every request.
        self.expected = token.encode("utf-8")

    def covers(self, path: str) -> bool:
        """Whether the gate applies to a path."""
        return path == PROTECTED_PREFIX or path.startswith(f"{PROTECTED_PREFIX}/")

    def accepts(self, scope: Scope) -> bool:
        """
        Whether the request carries the configured credential.

        `compare_digest` rather than `==` so that the time taken does not
        describe how much of a guess was right. It is not a complete defence -
        the length of the presented value is still observable - but the
        credential is long and random, which is what makes the remaining signal
        useless.
        """
        credential = presented_credential(scope)
        if credential is None:
            return False
        return hmac.compare_digest(credential, self.expected)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.covers(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        if self.accepts(scope):
            await self.app(scope, receive, send)
            return

        # The path is safe to log: no route here mints or accepts an identifier
        # for a document, so it names nothing. The header is not logged, in any
        # form - a rejected credential is still a credential, and a near miss in
        # a log file is a working one for whoever reads the log.
        logger.warning(
            "Refused a request to %s that carried no valid credential",
            scope.get("path", ""),
        )
        await unauthorized()(scope, receive, send)
