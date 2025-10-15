from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from config.firebase_config import FirebaseConfig
from config.auth_dependencies import get_current_user
from typing import Optional

router = APIRouter(prefix="/keys", tags=["API Keys"])


# ==========================================
# Modelos de datos (Schemas)
# ==========================================

class CreateKeyRequest(BaseModel):
    """
    Body to create a new API Key
    """
    device: str = Field(..., description="Device name that will use this key", min_length=1)
    name: str = Field(..., description="Descriptive name for the key", min_length=1)
    reserved: bool = Field(default=False, description="if the key is reserved or not")
    secretKey: str = Field(..., description="The secret key/API key", min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "device": "Production Server",
                "name": "OpenAI API Key",
                "reserved": True,
                "secretKey": "sk-proj-xxxxxxxxxxxxx"
            }
        }


class CreateKeyResponse(BaseModel):
    """
    Response to creating a new API key
    """
    success: bool
    message: str
    key_id: str
    data: dict

@router.get("/list")
async def list_keys(current_user: dict = Depends(get_current_user)):
    """
    List the API keys of the authenticated user from Firestore
    
    **Auth required:**
    
    Headers:
        Authorization: Bearer <firebase_id_token>
    
    Returns:
        dict: user Keys
    
    Example response:
        {
            "success": true,
            "user_id": "abc123xyz",
            "count": 2,
            "keys": [
                {
                    "id": "key123",
                    "name": "Key A",
                    "key": "sk-xxxxx",
                    "active": true,
                    "user": "abc123xyz",
                    "device": "smartTV",
                }
            ]
        }
    
    Errors:
        401: Token not provided, invalid, or expired
        500: Server error
    """
    try:
        user_id = current_user.get('uid')
        print("User ID extraído del token:", user_id)
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="No se pudo obtener el ID del usuario del token"
            )
        
        db = FirebaseConfig.get_firestore()
        
        keys_collection = db.collection('keys')
        
        query = keys_collection.where('user', '==', user_id)
        docs = query.stream()
        
        keys_list = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            keys_list.append(data)
        
        return {
            "success": True,
            "user_id": user_id,
            "count": len(keys_list),
            "keys": keys_list
        }
    
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las claves de API: {str(e)}"
        )


@router.post("/create", response_model=CreateKeyResponse)
async def create_key(
    key_data: CreateKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new API key for the authenticated user in Firestore
    
    **Auth Required:**
    
    Headers:
        Authorization: Bearer <firebase_id_token>
    
    Body:
        {
            "device": "Smartphone",
            "name": "Key for Mobile App",
            "reserved": true,
            "secretKey": "sk-proj-xxxxxxxxxxxxx"
        }
    
    Returns:
        dict: Details of the created key
    
    Example response:
        {
            "success": true,
            "message": "Key creada exitosamente",
            "key_id": "abc123def456",
            "data": {
                "device": "Production Server",
                "name": "OpenAI API Key",
                "reserved": true,
                "secretKey": "sk-proj-xxxxx...",
                "user": "user_id_from_token"
            }
        }
    
    Errors:
        401: Token not provided, invalid, or expired
        500: Server error
    """
    try:
        user_id = current_user.get('uid')
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="No se pudo obtener el ID del usuario del token"
            )
        
        db = FirebaseConfig.get_firestore()

        new_key_data = {
            "device": key_data.device,
            "name": key_data.name,
            "reserved": key_data.reserved,
            "secretKey": key_data.secretKey,
            "user": user_id  # ⭐
        }

        doc_ref = db.collection('keys').add(new_key_data)
        
        key_id = doc_ref[1].id
        
        return {
            "success": True,
            "message": "Key creada exitosamente",
            "key_id": key_id,
            "data": {
                "device": key_data.device,
                "name": key_data.name,
                "reserved": key_data.reserved,
                "secretKey": key_data.secretKey,
                "user": user_id
            }
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la clave de API: {str(e)}"
        )