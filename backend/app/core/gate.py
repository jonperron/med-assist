"""
What a gate in front of the analysis routes is made of.

There is one today - `RequireKnownOrigin` - and there was a second, the shared
credential, until it was removed. This module holds everything that is not the
question a gate asks: which paths it covers, how the path is recovered from an
ASGI scope, which scope types are checked at all, and how a refusal is delivered
on an HTTP request versus a WebSocket handshake.

Kept separate from its one subclass because `routed_path` encodes a rule that is
easy to get wrong and silent when it is: Starlette's router matches on the path
with `root_path` stripped, so an application served behind `--root-path
/med-assist` routes `/med-assist/api/analyze` to the route registered as
`/api/analyze`. A gate that compared `scope["path"]` would not recognise it,
would call through without a word, and the route would run - the control absent
on exactly the deployment that put a proxy in front, which is the deployment the
controls exist for. That was a real finding against the first gate, and writing
the rule a second time is how it comes back.
"""

import logging

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Where the analysis routes are mounted. A gate covers this prefix and nothing
# else: liveness, readiness, the root and the schema endpoints are outside it.
# `test_origin_gate.py` pins the exact set so that a router mounted outside
# `/api` cannot ship ungated with nothing failing.
PROTECTED_PREFIX = "/api"

# The scope types a gate inspects. `websocket` is covered as well as `http`
# even though no route here is one today: an exemption for every scope that is
# not HTTP would mean the first `/api` socket anyone adds ships ungated, with no
# test failing and nothing to warn its author. `lifespan` and anything else
# passes through untouched - it carries no path.
GUARDED_SCOPES = ("http", "websocket")

# The close code for a refused handshake. There is no 401 or 403 on a socket
# that was never opened, and 1008 is the policy-violation code. Uvicorn
# translates a close sent before accept into an HTTP 403 on the handshake, so a
# real client sees that rather than this code; nothing should come to depend on
# the code reaching anyone.
POLICY_VIOLATION = 1008

# How much of a refused request's path is written to the log. Long enough to
# tell `/api/analyze` from `/api/analyze/stream` and to show a caller probing
# for something else, short enough that a refusal nobody authenticated cannot
# fill the container's rotating log with one request.
LOGGED_PATH_LIMIT = 100


def routed_path(scope: Scope) -> str:
    """
    The path the router will match on, which is not always `scope["path"]`.

    An application mounted behind a prefix carries that prefix in `root_path`,
    and Starlette strips it before matching. A gate has to strip it *exactly*
    the way the router does, or it judges a path the router never sees. See the
    module docstring for what that costs.

    The rule is deliberately not "strip the prefix when the path starts with
    it". Starlette only strips when what follows the prefix is a separator, and
    the difference is a bypass rather than a nicety: under `--root-path /a`, a
    request for `/api/analyze` still routes to `/api/analyze`, because the
    character after `/a` is `p` and not `/`. A gate that stripped on
    `startswith` would compare `pi/analyze`, find it outside the prefix, and
    call through - the control absent again, on a different mount prefix.

    This mirrors `starlette._utils.get_route_path` rather than calling it: that
    module is private and a runtime dependency on it would break the service on
    an upgrade that moved it. `test_gate_paths.py` compares this function
    against Starlette's across a table of cases, so a divergence fails a test
    instead of silently opening a hole.

    :param scope: The ASGI connection scope.
    :return: The path with any mount prefix removed.
    """
    path = scope.get("path", "")
    root_path = scope.get("root_path", "")
    if not root_path:
        return path
    if not path.startswith(root_path):
        return path
    if path == root_path:
        return ""
    if path[len(root_path)] == "/":
        return path[len(root_path) :]
    return path


def loggable(path: str) -> str:
    """
    Render a caller-supplied path as one line of printable ASCII, bounded.

    `unicode_escape` turns a newline into a backslash-n and an escape byte into
    a backslash-x1b, so a request target cannot forge a log record or drive the
    terminal an operator is reading in. The cap bounds what one refusal can
    write, since the refusal is reachable without a credential and the container
    log rotates.

    :param path: The routed path, as the caller sent it.
    :return: The path, escaped and truncated.
    """
    escaped = path.encode("unicode_escape").decode("ascii")
    if len(escaped) <= LOGGED_PATH_LIMIT:
        return escaped
    return f"{escaped[:LOGGED_PATH_LIMIT]}..."


def covers(path: str) -> bool:
    """
    Whether the gates apply to a routed path.

    :param path: A path as `routed_path` reports it.
    :return: True for the analysis prefix and everything under it.
    """
    return path == PROTECTED_PREFIX or path.startswith(f"{PROTECTED_PREFIX}/")


class CoveredRouteGate:
    """
    Refuse a request to the analysis routes that fails this gate's question.

    A subclass supplies `accepts`, the refusal body, and the sentence written to
    the log. This class owns everything else, and three of its choices are
    deliberate:

    - **A CORS preflight never reaches a gate.** `CORSMiddleware` is mounted
      outside it and answers `OPTIONS` itself, which it has to: a browser sends
      no body on a preflight, so a gate that judged one would refuse the request
      that exists to ask whether the real one may be sent.
    - **The refusal is written straight to `send`**, like the size ceiling's
      413, rather than returned through the router. That is why CORS belongs
      outside a gate and caching control outside that: the refusal picks up the
      allow-origin header on the way out, and `no-store` with it. Without the
      first, a browser sees an opaque network error instead of a status the
      interface can report.
    - **Nothing reads the body.** The question is answered from the request
      headers, which is the whole reason this is ASGI middleware rather than a
      route dependency: FastAPI parses a multipart body before it solves any
      dependency, so a dependency would refuse the caller only after the server
      had spooled up to the whole 50MB ceiling into `TMPDIR`. A refused document
      is never written to disk.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def accepts(self, scope: Scope) -> bool:
        """
        Whether this gate lets the request through.

        :param scope: The ASGI connection scope.
        :return: True to call the application below.
        """
        raise NotImplementedError

    def refusal(self) -> JSONResponse:
        """The response sent to an HTTP request this gate refused."""
        raise NotImplementedError

    def refusal_reason(self) -> str:
        """
        The sentence logged with the refused path.

        Held apart from the response so that what is written to the log and what
        is sent to the caller cannot drift, and so that neither can grow a
        detail the other should not carry.
        """
        raise NotImplementedError

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in GUARDED_SCOPES:
            await self.app(scope, receive, send)
            return

        path = routed_path(scope)
        if not covers(path):
            await self.app(scope, receive, send)
            return

        if self.accepts(scope):
            await self.app(scope, receive, send)
            return

        # The path is escaped and capped before it is logged, because at this
        # point it is not a route - it is whatever the caller put in the request
        # target. The gate fires on the whole `/api` prefix, before any routing,
        # so `/api/<anything>` reaches this line, and uvicorn percent-decodes
        # the target into `scope["path"]`: `%0A` arrives as a real newline and
        # `%1B` as a real escape byte. Logged raw, an unauthenticated caller
        # forges log lines - including plausible copies of this service's own -
        # and injects terminal escapes into whatever an operator reads the log
        # in. `unicode_escape` renders both as text, and the cap bounds a single
        # refusal's contribution to a rotating log an attacker would otherwise
        # roll real records out of.
        #
        # What the request carried is still never logged - in particular not
        # the origin, which is attacker-controlled text like the path and would
        # need the same escaping to be safe.
        logger.warning(
            "Refused a request to %s: %s", loggable(path), self.refusal_reason()
        )

        if scope["type"] == "websocket":
            # The handshake is refused before it is accepted. The connect
            # message is received first because a server is entitled to expect
            # the application to read it.
            await receive()
            await send({"type": "websocket.close", "code": POLICY_VIOLATION})
            return

        await self.refusal()(scope, receive, send)
