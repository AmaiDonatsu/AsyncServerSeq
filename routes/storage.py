from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from config.firebase_config import FirebaseConfig
from typing import Optional
import io
from datetime import timedelta

router = APIRouter(prefix="/storage", tags=["Cloud Storage"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder: Optional[str] = Query(None, description="Carpeta destino en Cloud Storage")
):
    """
    Sube un archivo a Firebase Cloud Storage
    
    Args:
        file: Archivo a subir
        folder: Carpeta opcional donde guardar el archivo
    
    Returns:
        dict: Información del archivo subido y URL pública
    """
    try:
        bucket = FirebaseConfig.get_bucket()
        
        # Construir la ruta del archivo
        file_path = f"{folder}/{file.filename}" if folder else file.filename
        
        # Crear blob y subir archivo
        blob = bucket.blob(file_path)
        
        # Leer contenido del archivo
        contents = await file.read()
        
        # Subir a Firebase Storage
        blob.upload_from_string(
            contents,
            content_type=file.content_type
        )
        
        # Hacer el archivo público (opcional)
        blob.make_public()
        
        return {
            "success": True,
            "message": "Archivo subido correctamente",
            "file_name": file.filename,
            "file_path": file_path,
            "content_type": file.content_type,
            "size_bytes": len(contents),
            "public_url": blob.public_url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir el archivo: {str(e)}"
        )


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """
    Descarga un archivo desde Firebase Cloud Storage
    
    Args:
        file_path: Ruta completa del archivo en Storage (incluye carpetas)
    
    Returns:
        StreamingResponse: El archivo para descargar
    """
    try:
        bucket = FirebaseConfig.get_bucket()
        blob = bucket.blob(file_path)
        
        # Verificar si el archivo existe
        if not blob.exists():
            raise HTTPException(
                status_code=404,
                detail=f"El archivo '{file_path}' no existe"
            )
        
        # Descargar el archivo
        file_bytes = blob.download_as_bytes()
        
        # Obtener el nombre del archivo
        file_name = file_path.split('/')[-1]
        
        # Retornar como streaming response
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=blob.content_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={file_name}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al descargar el archivo: {str(e)}"
        )


@router.get("/list")
async def list_files(
    prefix: Optional[str] = Query(None, description="Filtrar por carpeta/prefijo")
):
    """
    Lista todos los archivos en Cloud Storage
    
    Args:
        prefix: Opcional - Filtrar archivos por carpeta o prefijo
    
    Returns:
        dict: Lista de archivos con sus metadatos
    """
    try:
        bucket = FirebaseConfig.get_bucket()
        
        # Listar blobs con prefijo opcional
        blobs = bucket.list_blobs(prefix=prefix)
        
        files = []
        for blob in blobs:
            files.append({
                "name": blob.name,
                "size_bytes": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "public_url": blob.public_url if blob.public_url else None
            })
        
        return {
            "success": True,
            "count": len(files),
            "files": files
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar archivos: {str(e)}"
        )


@router.delete("/delete/{file_path:path}")
async def delete_file(file_path: str):
    """
    Elimina un archivo de Firebase Cloud Storage
    
    Args:
        file_path: Ruta completa del archivo en Storage
    
    Returns:
        dict: Confirmación de eliminación
    """
    try:
        bucket = FirebaseConfig.get_bucket()
        blob = bucket.blob(file_path)
        
        # Verificar si el archivo existe
        if not blob.exists():
            raise HTTPException(
                status_code=404,
                detail=f"El archivo '{file_path}' no existe"
            )
        
        # Eliminar el archivo
        blob.delete()
        
        return {
            "success": True,
            "message": f"Archivo '{file_path}' eliminado correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar el archivo: {str(e)}"
        )


@router.get("/url/{file_path:path}")
async def get_signed_url(
    file_path: str,
    expiration_minutes: int = Query(60, description="Minutos hasta que expire la URL")
):
    """
    Genera una URL firmada temporal para acceder a un archivo privado
    
    Args:
        file_path: Ruta del archivo en Storage
        expiration_minutes: Tiempo de expiración en minutos (default: 60)
    
    Returns:
        dict: URL firmada con tiempo de expiración
    """
    try:
        bucket = FirebaseConfig.get_bucket()
        blob = bucket.blob(file_path)
        
        # Verificar si el archivo existe
        if not blob.exists():
            raise HTTPException(
                status_code=404,
                detail=f"El archivo '{file_path}' no existe"
            )
        
        # Generar URL firmada
        url = blob.generate_signed_url(
            expiration=timedelta(minutes=expiration_minutes),
            version="v4"
        )
        
        return {
            "success": True,
            "file_path": file_path,
            "signed_url": url,
            "expires_in_minutes": expiration_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar URL firmada: {str(e)}"
        )
