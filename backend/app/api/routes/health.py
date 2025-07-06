from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
@router.get("/healthz")
async def health_check():
    """
    Health check endpoint to verify if the API is running.
    """
    return JSONResponse(status_code=200, content="API is running smoothly.")
