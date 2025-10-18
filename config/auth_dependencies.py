"""
Authentication dependencies for FastAPI
Handle Firebase Authentication token verification
"""

from fastapi import Header, HTTPException, status
from firebase_admin import auth
from config.firebase_config import FirebaseConfig
from typing import Optional


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    
    print("=" * 60)
    print("DEBUG - get_current_user")
    print(f"Authorization header: {authorization}")
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó el token de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    parts = authorization.split()
    print(f"Parts after split: {len(parts)} parts")
    
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido. Use: 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    print(f"Token extraído (primeros 50 chars): {token[:50]}...")
    print(f"Token length: {len(token)}")
    
    try:
        decoded_token = FirebaseConfig.verify_token(token)
        print(f"Token decodificado exitosamente. UID: {decoded_token.get('uid')}")
        print("=" * 60)
        return decoded_token
        
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o mal formado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha expirado. Por favor, inicie sesión nuevamente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token ha sido revocado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error al verificar el token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_user_id(user: dict = None) -> str:
    """
        Gets the user ID from the decoded token
        Args:
        user: Decoded token from Firebase Authentication
    """
    return user.get('uid')
