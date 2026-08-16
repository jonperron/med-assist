import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analysis_router,
    extractions_router,
    health_router,
    mock_router,
    uploads_router,
)
from app.core.middleware import forbid_caching, reject_oversized_requests

logger = logging.getLogger(__name__)

DEVELOPMENT = "development"
PRODUCTION = "production"


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

    application = FastAPI(title="Med-Assist Backend")

    application.add_exception_handler(Exception, unexpected_failures_stay_generic)

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
