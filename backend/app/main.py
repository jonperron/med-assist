import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analysis_router,
    health_router,
    mock_router,
)
from app.core.access import (
    ACCESS_TOKEN_VARIABLE,
    RequireAccessToken,
    configured_access_token,
)
from app.core.config import CORSConfiguration
from app.core.dependencies import get_entity_extractor
from app.core.middleware import LimitRequestSize, forbid_caching

logger = logging.getLogger(__name__)


DEVELOPMENT = "development"
PRODUCTION = "production"


@asynccontextmanager
async def load_the_model_before_serving(
    application: FastAPI,
) -> AsyncIterator[None]:
    """
    Read the weights at startup, and record whether it worked.

    Loading takes seconds on a CPU. Left to the first request, that caller paid
    for it - and every later caller paid again whenever the load failed, since
    `lru_cache` does not memoise an exception. Doing it here means the cost is
    the process's, and `model_loaded` is what the routes and `/readyz` read
    afterwards.

    Uvicorn opens its sockets only after this returns, so nothing is served
    during the load: the port is closed, not slow. The threadpool call is
    discipline rather than concurrency - blocking work does not belong on the
    loop even when nothing else is using it yet.
    """
    application.state.model_loaded = False
    try:
        await run_in_threadpool(get_entity_extractor)
        application.state.model_loaded = True
        logger.info("The NER model is loaded and the service is ready")
    except Exception as exc:  # pylint: disable=W0718
        # Anything a missing, unreadable or misconfigured model directory can
        # raise. The process stays up and answers 503 on /readyz rather than
        # crash-looping, which says nothing about why. The type is safe to log:
        # no document has been read yet.
        logger.error("The NER model failed to load (%s)", type(exc).__name__)

    yield


async def unexpected_failures_stay_generic(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Answer anything that escaped a route with a fixed body, and log a name.

    Without this, an exception reaching Starlette's default handler is logged
    with its full traceback - and the values in scope on these paths are
    document text and the entities read from it. The request path is safe to
    log: no route mints an identifier for a document, so it carries none.
    """
    logger.error(
        "Unhandled error serving %s (%s)", request.url.path, type(exc).__name__
    )
    return JSONResponse(
        status_code=500,
        content={"detail": {"message": "Internal server error"}},
    )


async def malformed_requests_stay_generic(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Answer a malformed request with the same fixed body every refusal uses.

    FastAPI's own handler for a validation error reports the value it rejected
    under an `input` key. On the analysis route the body *is* the documents, so
    a client that sends the text as a form field instead of a file part has
    that text reflected back - the one response on this service that could
    carry clinical content, and the only one outside the fixed envelope the
    frontend parses. Neither the value nor the field path is echoed.
    """
    logger.error("Malformed request to %s", request.url.path)
    return JSONResponse(
        status_code=422,
        content={"detail": {"message": "The request body could not be read."}},
    )


def create_app(app_env: str | None = None) -> FastAPI:
    """
    Build the application.

    :param app_env: Which environment to build for. Defaults to `APP_ENV`, and
        to production when that is unset, so development-only endpoints are
        never mounted by accident - including when a tool imports this module
        to export the API schema.
    :return: The configured application.
    """
    environment = app_env or os.getenv("APP_ENV", PRODUCTION)

    application = FastAPI(
        title="Med-Assist Backend", lifespan=load_the_model_before_serving
    )

    application.add_exception_handler(Exception, unexpected_failures_stay_generic)
    application.add_exception_handler(
        RequestValidationError, malformed_requests_stay_generic
    )

    access_token = configured_access_token()

    # The last one registered runs first, so the stack is forbid_caching, then
    # CORS, then the credential gate if there is one, then the size ceiling,
    # then the router.
    #
    # The order of the middle two is load-bearing. LimitRequestSize writes its
    # 413 straight to `send` rather than returning through the router, so a
    # refusal only carries CORS headers if CORSMiddleware is outside it -
    # otherwise the browser sees an opaque network error and the frontend's
    # `too_large` branch is unreachable. Putting CORS outside costs nothing: it
    # forwards `receive` untouched, so the ceiling still wraps the channel the
    # multipart parser reads from, which is the whole reason it is ASGI
    # middleware.
    #
    # The allowed origins are read from the environment, the same way the
    # frontend reads the API's own URL from `NEXT_PUBLIC_API_URL`. As a literal
    # here, the two ends of one connection were configured by different
    # mechanisms and any host other than localhost needed a source edit.
    # Unset, the value is still the local frontend origin - never a wildcard,
    # which a browser refuses on a credentialed response anyway.
    application.add_middleware(LimitRequestSize)

    # Registered after the ceiling so that it runs before it: a caller with no
    # credential is refused on its headers, and the body it was sending is
    # never read, let alone spooled to TMPDIR and measured. Mounted only when a
    # credential is configured, and the two cases are logged because the
    # difference between them is the whole security posture of the deployment -
    # a mistyped variable name would otherwise leave the routes open and look
    # exactly like a service that had been locked down.
    if access_token:
        application.add_middleware(RequireAccessToken, token=access_token)
        logger.info(
            "The analysis routes require a bearer credential. The browser "
            "interface cannot supply one; put an authenticating proxy in front."
        )
    else:
        logger.warning(
            "No %s is configured: the analysis routes answer any client that "
            "can reach this port. CORS does not change that.",
            ACCESS_TOKEN_VARIABLE,
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(CORSConfiguration().allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.middleware("http")(forbid_caching)

    # Include routers from the API layer
    application.include_router(health_router, tags=["Health Check"])
    application.include_router(
        analysis_router, prefix="/api", tags=["Stateless Analysis"]
    )
    if environment == DEVELOPMENT:
        application.include_router(mock_router)

    @application.get("/")
    async def root():
        return {
            "message": "Welcome to Med-Assist API. Use /docs for API documentation."
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
