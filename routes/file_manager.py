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
    
    file_path = get_file_path_dir(user_id, filename)

    if not verify_file(file_path):
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
    return f"/files/access-image?token={token}"


@router.get("/{image_id}/signed-url")
async def get_signed_url(
    image_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a signed URL for accessing an image temporarily
    
    Args:
        image_id: Name of the image file
        current_user: Authenticated user data from Firebase
    
    Returns:
        dict: Contains the signed URL (relative path)
        
    Example:
        GET /files/photo.jpg/signed-url
        Headers: Authorization: Bearer <token>
        
        Response: {"signedUrl": "/files/access-image?token=..."}
    """
    user_id = current_user.get('uid')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo obtener el ID del usuario"
        )
    
    image_path = get_user_image(user_id, image_id)

    if not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada"
        )

    if not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada"
        )
    
    # Generar URL firmada
    signed_url = generate_signed_url(image_path, expires_in_seconds=3600)
    
    return {"signedUrl": signed_url}


@router.get("/access-image")
async def access_image_with_token(token: str):
    """
    Access an image using a signed token
    
    This endpoint allows temporary access to an image without authentication,
    using a time-limited signed token.
    
    Args:
        token: Signed token containing the image path
    
    Returns:
        FileResponse: The image file
        
    Raises:
        HTTPException: If token is invalid, expired, or image doesn't exist
        
    Example:
        GET /files/access-image?token=eyJhbGc...
    """
    try:
        # Verificar y decodificar el token (expira en 1 hora por defecto)
        data = serializer.loads(
            token,
            salt="image-access",
            max_age=3600  # 1 hora
        )
        
        image_path = data.get("image_path")
        
        if not image_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido: no contiene ruta de imagen"
            )
        
        # Verificar que el archivo existe
        file_path = Path(image_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Imagen no encontrada"
            )
        
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La ruta no es un archivo válido"
            )
        
        # Determinar el tipo de contenido
        ext = file_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg"
        }
        media_type = media_types.get(ext, "application/octet-stream")
        
        print(f"🔓 Acceso temporal concedido a: {file_path.name}")
        
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name
        )
        
    except SignatureExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha expirado. Solicita una nueva URL firmada."
        )
    
    except BadSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o corrupto"
        )
    
    except Exception as e:
        print(f"✗ Error al procesar token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la solicitud"
        )

# verifications
# ===================================================

def get_user_image(user_id: str, image_id: str) -> str:
    """
    Get the full path of a user's image if it exists and is valid
    
    Args:
        user_id: User ID
        image_id: Image filename
    
    Returns:
        str: Full path to the image or empty string if not found/invalid
    """
    if not validate_image_file(image_id):
        return ""
    
    if ".." in image_id or "/" in image_id or "\\" in image_id:
        return ""
    
    user_dir = STORAGE_BASE_DIR / user_id
    image_path = user_dir / image_id
    
    try:
        image_path = image_path.resolve()
        user_dir = user_dir.resolve()
        if not str(image_path).startswith(str(user_dir)):
            return ""
    except Exception:
        return ""
    
    if image_path.exists() and image_path.is_file():
        return str(image_path)
    return ""

def get_file_path_dir(user_id: str, filename: str) -> Path:
    """
    Get the full file path for a user's file
    
    Args:
        user_id: User ID
        filename: Name of the file

    Returns:
        Path: Full file path
    """

    file_path = STORAGE_BASE_DIR / user_id / filename

    return file_path
def verify_file(file_path: Path) -> bool:
    """
    Verify if a file exists for a given user
    
    Args:
        user_id: User ID
        filename: Name of the file

    Returns:
        bool: True if file exists, False otherwise
    """
    return file_path.exists()

