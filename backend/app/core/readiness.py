"""Whether the model is loaded, and the guard that refuses work until it is.

The weights are read once, by the lifespan handler in `app.main`. Nothing else
should read them: `lru_cache` does not memoise an exception, so a route that
builds the extractor after a failed startup re-attempts the whole multi-second
load on every request, in a worker thread, forever. The flag turns that into one
refusal.
"""

from fastapi import HTTPException, Request

MODEL_NOT_LOADED = "The service is starting up. Try again shortly."


def model_is_loaded(request: Request) -> bool:
    """
    Whether this application has the model in memory.

    An application whose lifespan never ran - a router mounted in a test, or an
    embedding that manages its own startup - has made no claim either way, and a
    guard is not the place to invent one, so the absent flag reads as ready.
    """
    return bool(getattr(request.app.state, "model_loaded", True))


async def require_the_model(request: Request) -> None:
    """
    Refuse a request that needs the model before the model exists.

    :param request: The incoming request, for the application state.
    :raises HTTPException: 503 while the model is not loaded.
    """
    if not model_is_loaded(request):
        raise HTTPException(
            status_code=503,
            detail={"message": MODEL_NOT_LOADED},
        )
