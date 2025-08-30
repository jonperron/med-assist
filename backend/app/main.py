import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health_router, mock_router, uploads_router, extractions_router
from app.core.exceptions import (
    MedAssistBaseException,
    FileProcessingError,
    ValidationError,
    StorageError,
)
from app.core.exception_handlers import (
    med_assist_exception_handler,
    file_processing_exception_handler,
    validation_exception_handler,
    storage_exception_handler,
)

app = FastAPI(title="Med-Assist Backend")

# Add exception handlers
app.add_exception_handler(MedAssistBaseException, med_assist_exception_handler)
app.add_exception_handler(FileProcessingError, file_processing_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(StorageError, storage_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from the API layer
app.include_router(health_router, tags=["Health Check"])
app.include_router(uploads_router, prefix="/api", tags=["Document Uploads"])
app.include_router(extractions_router, prefix="/api", tags=["Text Extractions"])

if os.getenv("APP_ENV", "development") == "development":
    app.include_router(mock_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Med-Assist API. Use /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
