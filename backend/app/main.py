import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import (
    analysis_router,
    extractions_router,
    health_router,
    mock_router,
    uploads_router,
)
from app.core.middleware import forbid_caching, reject_oversized_requests

app = FastAPI(title="Med-Assist Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The last one registered runs first, so forbid_caching wraps everything below
# it - including a refusal - and an oversized body is refused before it is read.
app.middleware("http")(reject_oversized_requests)
app.middleware("http")(forbid_caching)

# Include routers from the API layer
app.include_router(health_router, tags=["Health Check"])
app.include_router(analysis_router, prefix="/api", tags=["Stateless Analysis"])
app.include_router(uploads_router, prefix="/api", tags=["Document Uploads"])
app.include_router(extractions_router, prefix="/api", tags=["Text Extractions"])

# Default to production so the mock endpoints require an explicit opt-in.
if os.getenv("APP_ENV", "production") == "development":
    app.include_router(mock_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Med-Assist API. Use /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
