from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import FileResponse
from config.auth_dependencies import get_current_user
import os
from pathlib import Path
from typing import List


router = APIRouter(
    prefix="/files",
    tags=["files"]
)


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
# Maximum file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024

STORAGE_BASE_DIR = Path("static/storage")


def validate_image_file(filename: str) -> bool:
    """
    Validates if the file has an allowed image extension
    
    Args:
        filename: Name of the file to validate
    
    Returns:
        bool: True if the extension is allowed
    """
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


@router.post("/upload-image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload an image file for an authenticated user
    
    The file will be stored in: static/storage/{user_id}/{filename}
    
    Args:
        file: Image file to upload (.png, .jpg, .jpeg)
        current_user: Authenticated user data from Firebase
    
    Returns:
        dict: Information about the uploaded file
        
    Raises:
        HTTPException: If file validation fails
    """
    
    user_id = current_user.get('uid')
    user_email = current_user.get('email', 'unknown')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo obtener el ID del usuario"
        )
    
    print(f"📤 Upload request from user: {user_email} (ID: {user_id})")
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene nombre"
        )
    
    if not validate_image_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Solo se aceptan: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    contents = await file.read()
    file_size = len(contents)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo es demasiado grande. Tamaño máximo: {MAX_FILE_SIZE / (1024*1024)}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío"
        )
    
    try:
        user_dir = STORAGE_BASE_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = user_dir / file.filename
        
        with open(file_path, "wb") as f:
            f.write(contents)
        
        print(f"✓ Imagen guardada exitosamente: {file_path}")
        
        return {
            "message": "Imagen subida exitosamente",
            "user_id": user_id,
            "user_email": user_email,
            "filename": file.filename,
            "file_size": file_size,
            "file_path": str(file_path),
            "relative_path": f"storage/{user_id}/{file.filename}"
        }
        
    except Exception as e:
        print(f"✗ Error al guardar la imagen: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar la imagen: {str(e)}"
        )


@router.get("/list-images")
async def list_user_images(
    current_user: dict = Depends(get_current_user)
):
    """
    List all images uploaded by the authenticated user
    
    Args:
        current_user: Authenticated user data from Firebase
    
    Returns:
        dict: List of images belonging to the user
    """
    
    user_id = current_user.get('uid')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo obtener el ID del usuario"
        )
    
    user_dir = STORAGE_BASE_DIR / user_id
    
    if not user_dir.exists():
        return {
            "user_id": user_id,
            "images": [],
            "total": 0
        }
    
    images = []
    for file_path in user_dir.iterdir():
        if file_path.is_file() and validate_image_file(file_path.name):
            images.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "relative_path": f"storage/{user_id}/{file_path.name}"
            })
    
    return {
        "user_id": user_id,
        "images": images,
        "total": len(images)
    }


@router.get("/get-image/{filename}")
async def get_image(
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific image file for the authenticated user
    
    This endpoint returns the actual image file that can be displayed in a browser
    or used in an <img> tag.
    
    Args:
        filename: Name of the image file to retrieve
        current_user: Authenticated user data from Firebase
    
    Returns:
        FileResponse: The image file
        
    Raises:
        HTTPException: If file doesn't exist or access is denied
        
    Example:
        GET /files/get-image/profile.png
        Headers: Authorization: Bearer <token>
    """
    
    user_id = current_user.get('uid')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo obtener el ID del usuario"
        )
    
    file_path = STORAGE_BASE_DIR / user_id / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada"
        )
    
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ruta especificada no es un archivo"
        )
    
    if not validate_image_file(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una imagen válida"
        )
    
    ext = Path(filename).suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }
    media_type = media_types.get(ext, "application/octet-stream")
    
    print(f"📷 Serving image: {filename} to user {user_id}")
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename
    )


@router.delete("/delete-image/{filename}")
async def delete_image(
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific image from the authenticated user's storage
    
    Args:
        filename: Name of the file to delete
        current_user: Authenticated user data from Firebase
    
    Returns:
        dict: Confirmation message
        
    Raises:
        HTTPException: If file doesn't exist or deletion fails
    """
    
    user_id = current_user.get('uid')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo obtener el ID del usuario"
        )
    
    file_path = STORAGE_BASE_DIR / user_id / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no encontrado"
        )
    
    # Validate that it's a file (not a directory)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ruta especificada no es un archivo"
        )
    
    try:
        file_path.unlink()
        print(f"✓ Imagen eliminada: {file_path}")
        
        return {
            "message": "Imagen eliminada exitosamente",
            "user_id": user_id,
            "filename": filename
        }
        
    except Exception as e:
        print(f"✗ Error al eliminar la imagen: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar la imagen: {str(e)}"
        )
    
# url Signed
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
import os
from itsdangerous import BadSignature, SignatureExpired

SECRET_KEY = f"{os.getenv('SECRET_KEY')}"
serializer = URLSafeTimedSerializer(SECRET_KEY)

def generate_signed_url(image_path: str, expires_in_seconds: int = 3600):
    """
    Genera una URL firmada temporal
    expires_in_seconds: por defecto 1 hora
    """
    token = serializer.dumps(
        {"image_path": image_path},
        salt="image-access"
    )
    return f"https://tu-dominio.com/api/images/signed/{token}"

@router.get("/api/images/signed/{token}")
async def get_signed_image(token: str):
    try:
        data = serializer.loads(
            token,
            salt="image-access",
            max_age=3600
        )
        image_path = data["image_path"]
        
        return FileResponse(image_path)
        
    except SignatureExpired:
        raise HTTPException(status_code=403, detail="URL expirada")
    except BadSignature:
        raise HTTPException(status_code=403, detail="URL inválida")