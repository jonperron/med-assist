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
from app.core.config import CORSConfiguration
from app.core.dependencies import get_entity_extractor
from app.core.middleware import LimitRequestSize, forbid_caching
from app.core.origin import ORIGIN_VARIABLE, RequireKnownOrigin

logger = logging.getLogger(__name__)


DEVELOPMENT = "development"
PRODUCTION = "production"

# The credential this service used to require, read here only to say that it is
# no longer read. A deployment configured against the previous version keeps a
# value in its environment and, if it followed the old guidance, a proxy rule
# injecting `Authorization: Bearer` on the way through. Both now do nothing, and
# nothing else would say so: Compose used to refuse to start without the
# variable, so its silence was a signal, and now its silence is just silence.
# That is a control which reads as protective and is not, which is worth three
# lines to make visible.
RETIRED_CREDENTIAL_VARIABLE = "API_ACCESS_TOKEN"


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
    ordinary startup fact to a warning.
    """
    # The allow-list is named because a refusal cannot be. The 403 body is
    # fixed and the refusal log deliberately omits the origin that was
    # rejected - it is attacker-controlled text - so without this line an
    # operator whose deployment refuses its own interface can see neither side
    # of the comparison. These origins are the operator's own configuration,
    # not anything a caller supplied, so they are safe to write down.
    #
    # The sentence about authentication is the honest description of this
    # service and is meant to be read as a warning: nothing here identifies a
    # caller. Anyone who can reach the port can submit documents and spend this
    # host's CPU. See deploy/README.md for what that means before a domain is
    # attached to it.
    logger.warning(
        "The analysis routes authenticate nobody. Anyone who can reach this "
        "port can submit documents. The only check is the origin allow-list in "
        "%s, which constrains browsers and nothing else. Configured origins: "
        "%s.",
        ORIGIN_VARIABLE,
        ", ".join(application.state.allowed_origins) or "(none)",
    )

    if os.getenv(RETIRED_CREDENTIAL_VARIABLE):
        logger.warning(
            "%s is set and is no longer read. The analysis routes stopped "
            "requiring a credential, so anything in front of this service that "
            "injects an Authorization header is enforcing nothing. Remove the "
            "variable, and replace that proxy rule with authentication of your "
            "own before treating this deployment as protected.",
            RETIRED_CREDENTIAL_VARIABLE,
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

    # Raises rather than falling back to something permissive, and raises here
    # rather than on the first request: a deployment that is misconfigured fails
    # while it is starting, where an operator is watching, instead of answering
    # callers it should have refused.
    allowed_origins = CORSConfiguration().allowed_origins
    # Held on the application so the lifespan can name them in the startup log
    # without reading the environment a second time, which a test that patches
    # the variable would then disagree with.
    application.state.allowed_origins = allowed_origins

    # The last one registered runs first, so the stack is forbid_caching, then
    # CORS, then the origin gate, then the size ceiling, then the router.
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

    # Registered after the ceiling so that it runs before it: a caller from an
    # origin this deployment does not serve is refused on its headers, and the
    # body it was sending is never read, let alone spooled to TMPDIR and
    # measured. A refused document never touches the filesystem.
    #
    # This is the only gate in front of the analysis routes, and it is not
    # authentication. It constrains browsers - a scripted caller writes whatever
    # `Origin` it likes, and a request carrying none is let through - so what it
    # closes is one site driving an upload through a visitor's browser, and
    # nothing else. Anyone who can reach this port can still submit documents.
    # That is a deliberate posture for an R&D deployment, written down in
    # deploy/README.md and warned about on the page itself.
    #
    # The allow-list is not private either. CORS is mounted outside the gate
    # because it has to answer preflights itself, and an `OPTIONS` preflight
    # naming an origin is answered 200 or 400 according to that origin. Anyone
    # who can reach the port can confirm a guess that way.
    application.add_middleware(RequireKnownOrigin, allowed_origins=allowed_origins)

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
