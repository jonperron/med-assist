from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.readiness import MODEL_NOT_LOADED, model_is_loaded
from app.schemas.errors import ErrorResponse

router = APIRouter()


@router.get("/healthz")
async def health_check() -> JSONResponse:
    """
    Liveness: the process is up and the event loop is answering.

    This says nothing about the model. Uvicorn opens its sockets only once the
    lifespan handler returns, so a served answer here already implies the load
    has finished one way or the other - use `/readyz` for which way.
    """
    return JSONResponse(status_code=200, content="API is running smoothly.")


@router.get(
    "/readyz",
    responses={
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
    },
)
async def readiness_check(request: Request) -> JSONResponse:
    """
    Readiness: the model is loaded, so an analysis will not wait for weights.

    Refuses with the same envelope and the same message as the routes that need
    the model, so a caller reads one answer rather than two. The body carries a
    fixed string - no path, no configuration, no reason.
    """
    if not model_is_loaded(request):
        raise HTTPException(status_code=503, detail={"message": MODEL_NOT_LOADED})

    return JSONResponse(status_code=200, content={"status": "ready"})
