from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health_router, uploads_router, extractions_router

app = FastAPI(title="Med-Assist Backend")

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


@app.get("/")
async def root():
    return {"message": "Welcome to Med-Assist API. Use /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
