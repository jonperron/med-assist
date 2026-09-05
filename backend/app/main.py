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
    BEARER_SCHEME,
    RequireAccessToken,
    configured_access_token,
)
from app.core.config import CORSConfiguration
from app.core.dependencies import get_entity_extractor
from app.core.middleware import LimitRequestSize, forbid_caching
from app.core.origin import ORIGIN_VARIABLE, RequireKnownOrigin

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

    The posture line is written here rather than in `create_app` because it
    describes a process that is starting, not an object that was built - a
    schema export imports this module and builds an application too, and it is
    not a deployment.

    Whether an operator sees it depends on the deployment's logging
    configuration, and by default they do not: uvicorn installs handlers on its
    own `uvicorn*` loggers only, so records from `app.*` fall through to
    `logging.lastResort`, which drops anything below WARNING. That is a real
    limit and it is written down rather than papered over by promoting an
    ordinary startup fact to a warning. Nothing security-relevant rests on it:
    the fail-open case this line used to mitigate - a mistyped variable leaving
    the routes open - cannot happen now that a missing credential stops the
    process.
    """
    # The allow-list is named because a refusal cannot be. The 403 body is
    # fixed and the refusal log deliberately omits the origin that was
    # rejected - it is attacker-controlled text - so without this line an
    # operator whose deployment refuses its own interface can see neither side
    # of the comparison. These origins are the operator's own configuration,
    # not anything a caller supplied, so they are safe to write down.
    logger.info(
        "The analysis routes require a bearer credential, and an origin in "
        "%s or a browser reporting a same-origin request. Configured origins: "
        "%s. The browser interface cannot supply the credential; put an "
        "authenticating proxy in front.",
        ORIGIN_VARIABLE,
        ", ".join(application.state.allowed_origins) or "(none)",
    )

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


def describe_the_credential(application: FastAPI) -> None:
    """
    Put the bearer scheme in the document the analysis routes already reference.

    The routes declare `security: [{bearerCredential: []}]` through
    `openapi_extra`, because the credential is checked in middleware and FastAPI
    can only infer a requirement from a route dependency. A requirement naming a
    scheme the document does not define is a dangling reference: a generated
    client sees the two statuses and still has no generated way to send the
    header. This defines it.

    It wraps `application.openapi` rather than rebuilding the document, so
    nothing here has to know how FastAPI assembles one. The wrapper is lazy -
    the schema is only built if something asks for it - and FastAPI caches the
    result in `openapi_schema`, so the addition is made once.

    :param application: The application whose schema gains the scheme.
    """
    generate = application.openapi

    def openapi_with_the_credential() -> dict:
        if application.openapi_schema:
            return application.openapi_schema
        schema = generate()
        schema.setdefault("components", {})["securitySchemes"] = {
            BEARER_SCHEME: {
                "type": "http",
                "scheme": "bearer",
                "description": (
                    "The deployment's shared credential. Required on the "
                    "analysis routes: the service refuses to start without one "
                    "configured. It identifies no one - it is one secret shared "
                    "by every caller - and the browser interface in this stack "
                    "cannot present it, so a deployment serving that interface "
                    "puts an authenticating proxy in front to add the header."
                ),
            }
        }
        return schema

    application.openapi = openapi_with_the_credential  # type: ignore[method-assign]


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

    # Both raise rather than fall back to something permissive, and both raise
    # here rather than on the first request: a deployment that is misconfigured
    # fails while it is starting, where an operator is watching, instead of
    # answering callers it should have refused.
    access_token = configured_access_token()
    allowed_origins = CORSConfiguration().allowed_origins
    # Held on the application so the lifespan can name them in the startup log
    # without reading the environment a second time, which a test that patches
    # the variable would then disagree with.
    application.state.allowed_origins = allowed_origins

    # The last one registered runs first, so the stack is forbid_caching, then
    # CORS, then the credential gate, then the origin gate, then the size
    # ceiling, then the router.
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

    # Both gates are registered after the ceiling so that they run before it: a
    # caller that fails either is refused on its headers, and the body it was
    # sending is never read, let alone spooled to TMPDIR and measured. A refused
    # document never touches the filesystem.
    #
    # The origin gate is registered first, so it runs second. That order is the
    # security-relevant half: a caller presenting no credential is refused with
    # 401 whatever origin it claimed, so an anonymous caller cannot read the
    # allow-list by watching a 403 turn into a 401 on the analysis routes. The
    # reverse order refuses the same requests and leaks the list while doing it.
    #
    # It does not make the allow-list private, and nothing here can. CORS is
    # mounted outside both gates because it has to answer preflights itself, and
    # an `OPTIONS` preflight naming an origin is answered 200 or 400 according
    # to that origin, with no credential involved. Anyone who can reach the port
    # can confirm a guess that way. See the decision entry's residual risk.
    application.add_middleware(RequireKnownOrigin, allowed_origins=allowed_origins)
    application.add_middleware(RequireAccessToken, token=access_token)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
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

    describe_the_credential(application)

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
