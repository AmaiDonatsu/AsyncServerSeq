from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/gemini", tags=["Gemini"])

class Blob(BaseModel):
    mime_type: str
    data: str  # Base64 encoded string

class Part(BaseModel):
    text: Optional[str] = None
    inline_data: Optional[Blob] = None

class Content(BaseModel):
    role: str
    parts: List[Part]

class ChatRequest(BaseModel):
    history: List[Content]
    model: Optional[str] = "gemini-2.0-flash-exp"
    config: Optional[Dict[str, Any]] = None

@router.post("/chat")
async def chat_with_gemini(request: ChatRequest):
    """
    Endpoint to interact with Google Gemini models.
    Accepts a conversation history including text and images.
    """
    try:
        # Initialize client
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client()

        # Prepare contents for the API
        contents = []
        for msg in request.history:
            parts = []
            for part in msg.parts:
                if part.text:
                    parts.append({"text": part.text})
                if part.inline_data:
                    parts.append({
                        "inline_data": {
                            "mime_type": part.inline_data.mime_type,
                            "data": part.inline_data.data
                        }
                    })
            contents.append({
                "role": msg.role,
                "parts": parts
            })

        response = client.models.generate_content(
            model=request.model,
            contents=contents,
            config=request.config
        )
        
        return {"response": response.text}

    except Exception as e:
        print(f"Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))
