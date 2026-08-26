import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analysis_router,
    extractions_router,
    health_router,
    mock_router,
    uploads_router,
)
from app.core.dependencies import get_entity_extractor
from app.core.middleware import forbid_caching, reject_oversized_requests

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
    document text and decrypted entities. The path is safe to log; it holds a
    file id at most.
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

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Frontend origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # The last one registered runs first, so forbid_caching wraps everything
    # below it - including a refusal - and an oversized body is refused before
    # it is read.
    application.middleware("http")(reject_oversized_requests)
    application.middleware("http")(forbid_caching)

    # Include routers from the API layer
    application.include_router(health_router, tags=["Health Check"])
    application.include_router(
        analysis_router, prefix="/api", tags=["Stateless Analysis"]
    )
    application.include_router(uploads_router, prefix="/api", tags=["Document Uploads"])
    application.include_router(
        extractions_router, prefix="/api", tags=["Text Extractions"]
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
