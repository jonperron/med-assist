"""HTTP middleware guarding the boundaries every clinical payload crosses."""

import logging
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Ceiling for a whole request body. A single document is capped at 10 MB by
# validate_upload_file, but that check runs once the body is already buffered,
# so the aggregate is refused here before anything is read.
MAX_REQUEST_SIZE_BYTES = 50 * 1024 * 1024

Handler = Callable[[Request], Awaitable[Response]]


async def reject_oversized_requests(request: Request, call_next: Handler) -> Response:
    """
    Refuse a body larger than the ceiling before it is read.

    Multipart parts above 1 MB are spooled to a temporary file by the server, so
    an unbounded body reaches the filesystem before any route code runs. The
    declared length is checked first; a body that lies about its length is still
    caught by the per-file limit.
    """
    declared_length = request.headers.get("content-length")

    if declared_length is not None:
        try:
            length = int(declared_length)
        except ValueError:
            length = -1

        if length > MAX_REQUEST_SIZE_BYTES:
            logger.warning(
                "Refused a request declaring %s bytes, over the %s byte ceiling",
                length,
                MAX_REQUEST_SIZE_BYTES,
            )
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={
                    "detail": {
                        "message": "Request too large",
                        "max_size_bytes": MAX_REQUEST_SIZE_BYTES,
                    }
                },
            )

    return await call_next(request)


async def forbid_caching(request: Request, call_next: Handler) -> Response:
    """Keep responses that may carry clinical content out of every cache."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
