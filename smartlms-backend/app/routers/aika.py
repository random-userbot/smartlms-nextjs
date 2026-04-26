from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
import asyncio
import os
import uuid
import shutil
from app.services.aika_service import aika_bot
from app.models.models import User
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/aika", tags=["Aika RAG Tutor"])

class AikaChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def chat_with_aika(req: AikaChatRequest, current_user: User = Depends(get_current_user)):
    """Send a message to Aika (the RAG-enabled chatbot) and get the response."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message provided")
        
    # Running sync code (langchain invoke) in a thread pool so it doesn't block the async event loop
    answer = await asyncio.to_thread(aika_bot.ask, req.message)
    
    return {"response": answer}

@router.post("/upload-material")
async def upload_material(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Allows teachers or users to upload a PDF or MD file into Aika's RAG knowledge base."""
    if not file.filename.endswith((".pdf", ".md", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF, MD, or TXT files are supported.")
        
    # Standardize metadata
    uploader_type = getattr(current_user, "role", "user")
    metadata = {
        "source": file.filename,
        "type": "uploaded_material",
        "uploader_id": str(current_user.id),
        "uploader_role": uploader_type
    }

    # Save temp file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    temp_dir = os.path.join(base_dir, "scratch", "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Safe filename
    ext = os.path.splitext(file.filename)[1]
    safe_name = f"{uuid.uuid4().hex}{ext}"
    temp_path = os.path.join(temp_dir, safe_name)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingest the file in a background thread to prevent blocking
        success = await asyncio.to_thread(aika_bot.ingest_document, temp_path, metadata)
        
        if success:
            return {"message": f"Successfully ingested {file.filename} into Aika's Knowledge Base."}
        else:
            raise HTTPException(status_code=500, detail="Failed to ingest document.")
            
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
