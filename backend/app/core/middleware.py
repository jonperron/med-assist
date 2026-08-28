"""HTTP middleware guarding the boundaries every clinical payload crosses."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Ceiling for a whole request body. A single document is capped at 10 MB by
# validate_upload_file, but that check runs once the body is already buffered,
# so the aggregate is refused here before anything is read.
MAX_REQUEST_SIZE_BYTES = 50 * 1024 * 1024

# The message every refusal in this module carries.
REQUEST_TOO_LARGE = "Request too large"

Handler = Callable[[Request], Awaitable[Response]]


class OversizedBody(Exception):
    """A body that ran past the ceiling while it was being received."""


def too_large(max_bytes: int) -> JSONResponse:
    """
    The one 413 this module answers with, however the size was discovered.

    The ceiling is passed in rather than read from the module constant: it is a
    constructor argument, and a body reporting a limit other than the one being
    enforced is the one field a client is meant to act on.
    """
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={
            "detail": {
                "message": REQUEST_TOO_LARGE,
                "max_size_bytes": max_bytes,
            }
        },
    )


class LimitRequestSize:
    """
    Refuse a body larger than the ceiling, whether or not it declares a length.

    Multipart parts above 1 MB are spooled to a temporary file by the server
    before any route code runs, so the ceiling has to bite while the body is
    being received rather than once a route can look at it. Two checks do that:

    - `Content-Length`, when the client declares one, refuses the request
      without reading a byte.
    - A counter on the receive channel refuses it mid-flight otherwise. A
      chunked body carries no declared length, so the header check never sees
      it, and the parser puts no ceiling of its own on a file part - only on
      the fields around it. Without this, a chunked upload is written to
      `TMPDIR` in full and *then* answered 413 by `validate_upload_file`, with
      the disk already spent.

    This is ASGI middleware rather than an `@app.middleware("http")` function
    because only ASGI middleware can wrap the receive channel: `BaseHTTPMiddleware`
    builds a fresh one for the app below it, so a dispatch function cannot reach
    the bytes the parser will actually read.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_SIZE_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def declared_length(self, scope: Scope) -> int:
        """
        Read `Content-Length`, treating an unreadable one as absent.

        The name is lowercased rather than compared to a lowercase literal.
        ASGI servers are required to normalise header names and uvicorn does,
        but this check is the cheap half of the ceiling and should not depend
        on that to run at all.
        """
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return -1
        return -1

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.declared_length(scope) > self.max_bytes:
            logger.warning(
                "Refused a request declaring more than the %d byte ceiling",
                self.max_bytes,
            )
            await too_large(self.max_bytes)(scope, receive, send)
            return

        received = 0
        exceeded = False
        started = False
        suppressing = False

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    # Raised rather than returned: the parser downstream is
                    # mid-part, and there is no message that would make it stop
                    # writing without also making it report a malformed body.
                    raise OversizedBody()
            return message

        async def limiting_send(message: Message) -> None:
            nonlocal started, suppressing
            if suppressing:
                return
            if exceeded and not started:
                # The app is answering a body that was cut off under it, and
                # what it makes of the truncation describes the wrong problem:
                # FastAPI reports a parser failure as 400. That answer is
                # dropped and replaced below by the refusal that says why the
                # body stopped.
                suppressing = True
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, limiting_send)
        except OversizedBody:
            # This middleware's own signal, raised into the app and caught on
            # the way back out. The refusal is sent below.
            pass
        except BaseExceptionGroup as group:
            # Starlette runs a streaming response body inside a task group, and
            # anyio wraps anything raised in a child task. A route that read the
            # body from inside such a generator would deliver the signal this
            # way, where a bare `except OversizedBody` does not match it and the
            # refusal would silently become a 500.
            rest = [
                exc for exc in group.exceptions if not isinstance(exc, OversizedBody)
            ]
            if rest:
                raise

        if not exceeded:
            return

        if started:
            # The status line was already on the wire when the body ran over, so
            # the refusal cannot be one, and the response the app sent has
            # already gone out intact. Raising here would reset the connection
            # and lose it, which is worse than the truncated read it reports.
            #
            # No route reaches this today: both endpoints declare a body field,
            # so FastAPI parses the form before any dependency or handler runs.
            # A route taking a raw `Request` and reading the body from inside a
            # streaming generator is what would make it reachable.
            logger.error(
                "A request ran past the %d byte ceiling after its response had "
                "begun; it was read short and could not be refused",
                self.max_bytes,
            )
            return

        logger.warning(
            "Refused a request that ran past the %d byte ceiling while being received",
            self.max_bytes,
        )
        await too_large(self.max_bytes)(scope, receive, send)


async def forbid_caching(request: Request, call_next: Handler) -> Response:
    """Keep responses that may carry clinical content out of every cache."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
