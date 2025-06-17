from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import shutil
import os

app = FastAPI(title="Med-Assist Backend")

# In-memory storage for extracted text (for now)
# In a real scenario, consider how to handle larger files or concurrent requests
extracted_data_store = {}

@app.post("/upload_document/")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint to upload a document.
    For now, it just saves the file name and type.
    Later, this will extract text.
    """
    # Basic placeholder - will be expanded for text extraction
    file_id = file.filename 
    extracted_data_store[file_id] = {
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded, text extraction pending"
    }
    # In a real app, you'd save the file or process it.
    # For now, let's just confirm receipt.
    # Example:
    # UPLOAD_DIR = "temp_uploads"
    # os.makedirs(UPLOAD_DIR, exist_ok=True)
    # file_path = os.path.join(UPLOAD_DIR, file.filename)
    # with open(file_path, "wb") as buffer:
    #     shutil.copyfileobj(file.file, buffer)
    
    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": file_id
        }
    )

@app.get("/get_extracted_text/{file_id}")
async def get_extracted_text(file_id: str):
    """
    Endpoint to retrieve extracted text (placeholder).
    """
    if file_id in extracted_data_store:
        # This will later return actual extracted entities
        return JSONResponse(
            status_code=200,
            content={
                "file_id": file_id,
                "data": extracted_data_store[file_id],
                "extracted_entities": "Placeholder for diseases, symptoms, treatments"
            }
        )
    return JSONResponse(status_code=404, content={"message": "File not found or not processed yet."})

@app.get("/")
async def root():
    return {"message": "Welcome to Med-Assist API. Use /docs for API documentation."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)