from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, model_validator
from config.firebase_config import FirebaseConfig
from config.auth_dependencies import get_current_user
from typing import Optional
from config.rate_limiter import limiter, RATE_LIMITS


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

@router.get("/list_available")
async def list_available_keys(current_user: dict = Depends(get_current_user)):
    """
    The available Keys are a keys with the field "reserved" set to False.
    """
    try:
        print("=" * 50)
        print("DEBUG - list_available_keys")
        print("Current user data:", current_user)
        user_id = current_user.get('uid')
        print("User ID extraído:", user_id)
        print("=" * 50)
        
        if not user_id:
            print("User ID not found in token")
            raise HTTPException(
                status_code=401,
                detail="No se pudo obtener el ID del usuario del token"
            )
        
        db = FirebaseConfig.get_firestore()
        keys_collection = db.collection('keys')
        query = keys_collection.where('reserved', '==', False).where('user', '==', user_id)
        docs = query.stream()

        available_keys = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            available_keys.append(data)

        return {
            "success": True,
            "count": len(available_keys),
            "keys": available_keys
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las claves disponibles: {str(e)}"
        )


class UpdateKeyRequest(BaseModel):
    is_available: bool = Field(...)
    device: str | None = Field(None, description="Device name") 

    @model_validator(mode='after')
    def check_logical_consistency(self):
        if not self.is_available and not self.device:
            raise ValueError('Si la clave no está disponible, debes especificar un dispositivo.')
        
        if self.is_available and self.device:
            self.device = None 
            
        return self

@router.put("/update_availability/{key_id}")
async def update_key_availability(
    key_id: str,
    update_data: UpdateKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the availability of an API key
    
    **Auth Required:**
    
    Headers:
        Authorization: Bearer <firebase_id_token>
    
    Body:
        {
            "is_available": false,
            "device": "Smartphone"
        }
    
    Returns:
        dict: Updated key details
    
    Errors:
        401: Token not provided, invalid, or expired
        403: User doesn't own this key
        404: Key not found
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
        key_ref = db.collection('keys').document(key_id)
        key = key_ref.get()

        if not key.exists:
            raise HTTPException(
                status_code=404,
                detail="Clave no encontrada"
            )

        key_data = key.to_dict()

        if key_data.get('user') != user_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para actualizar esta clave"
            )

        reserved = not update_data.is_available
        key_ref.update({"reserved": reserved, "device": update_data.device})

        return {
            "success": True,
            "message": "Disponibilidad de la clave actualizada",
            "key_id": key_id,
            "reserved": reserved,
            "is_available": update_data.is_available,
            "device": update_data.device
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar la disponibilidad de la clave: {str(e)}"
        )

@router.post("/create", response_model=CreateKeyResponse)
@limiter.limit(RATE_LIMITS["auth"])
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
    
@router.get("/get_by_device/{device}")
async def get_keys_by_device(
    device: str,
    actual_user: dict = Depends(get_current_user)
):
    """
    Get API keys filtered by device name for the authenticated user.
    
    **Auth Required:**
    
    Headers:
        Authorization: Bearer <firebase_id_token>  """
    try:
        user_id = actual_user.get('uid')
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="No se pudo obtener el ID del usuario del token"
            )
        
        db = FirebaseConfig.get_firestore()
        keys_collection = db.collection('keys')
        query = keys_collection.where('user', '==', user_id).where('device', '==', device)
        docs = query.stream()
        
        keys_list = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            keys_list.append(data)
        
        return {
            "success": True,
            "count": len(keys_list),
            "key": keys_list[0] if keys_list and len(keys_list) > 0 else None
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las claves por dispositivo: {str(e)}"
        )

@router.get("/get_reserved_keys")
async def get_reserved_keys(current_user: dict = Depends(get_current_user)):
    """
    Get all reserved API keys for the authenticated user.
    
    **Auth Required:**
    
    Headers:
        Authorization: Bearer <firebase_id_token> 
    """
    try:
        user_id = current_user.get('uid')
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="No se pudo obtener el ID del usuario del token"
            )
        
        db = FirebaseConfig.get_firestore()
        keys_collection = db.collection('keys')
        query = keys_collection.where('user', '==', user_id).where('reserved', '==', True)
        docs = query.stream()
        
        reserved_keys = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            reserved_keys.append(data)
        
        return {
            "success": True,
            "count": len(reserved_keys),
            "keys": reserved_keys
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las claves reservadas: {str(e)}"
        )