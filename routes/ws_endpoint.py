"""
WebSocket endpoint for real-time screen streaming
Handles authentication and device validation for mobile screen capture streaming
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState
from typing import Optional
from config.firebase_config import FirebaseConfig
from firebase_admin import auth
import json
import asyncio

router = APIRouter(prefix="/ws", tags=["WebSocket"])


# ==========================================
# Funciones auxiliares de autenticación
# ==========================================

async def verify_auth_token(token: str) -> Optional[dict]:
    """
    Verifica el token de Firebase Auth
    
    Args:
        token: Firebase ID token
    
    Returns:
        dict con la información del usuario si es válido, None si no lo es
    """
    try:
        decoded_token = FirebaseConfig.verify_token(token)
        return decoded_token
    except Exception as e:
        print(f"❌ Error al verificar token: {e}")
        return None


async def verify_secret_key(user_id: str, secret_key: str, device: str) -> bool:
    """
    Verifica que el secretKey y device correspondan a una key válida del usuario
    
    Args:
        user_id: ID del usuario autenticado
        secret_key: Secret key enviada en el request
        device: Nombre del dispositivo
    
    Returns:
        True si la key existe y pertenece al usuario, False en caso contrario
    """
    try:
        db = FirebaseConfig.get_firestore()
        keys_ref = db.collection('keys')
        
        # Buscar una key que coincida con user, secretKey y device
        query = keys_ref.where('user', '==', user_id)\
                        .where('secretKey', '==', secret_key)\
                        .where('device', '==', device)
        
        docs = list(query.stream())
        
        if len(docs) > 0:
            print(f"✅ Key válida encontrada para user={user_id}, device={device}")
            return True
        else:
            print(f"❌ No se encontró key válida para user={user_id}, device={device}")
            return False
            
    except Exception as e:
        print(f"❌ Error al verificar secret key: {e}")
        return False


# ==========================================
# Gestor de conexiones WebSocket
# ==========================================

class ConnectionManager:
    """
    Gestiona las conexiones WebSocket activas
    Permite broadcast y mensajes individuales
    """
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, device: str):
        """
        Acepta y registra una nueva conexión WebSocket
        """
        await websocket.accept()
        connection_id = f"{user_id}:{device}"
        self.active_connections[connection_id] = websocket
        print(f"🔌 Nueva conexión: {connection_id}")
        print(f"📊 Conexiones activas: {len(self.active_connections)}")
    
    def disconnect(self, user_id: str, device: str):
        """
        Elimina una conexión del registro
        """
        connection_id = f"{user_id}:{device}"
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            print(f"🔌 Desconexión: {connection_id}")
            print(f"📊 Conexiones activas: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """
        Envía un mensaje a una conexión específica
        """
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """
        Envía un mensaje a todas las conexiones activas
        """
        for connection in self.active_connections.values():
            if connection.client_state == WebSocketState.CONNECTED:
                await connection.send_text(message)


# Instancia global del gestor de conexiones
manager = ConnectionManager()


# ==========================================
# Endpoint WebSocket
# ==========================================

@router.websocket("/stream")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Firebase Auth ID token"),
    secretKey: str = Query(..., description="Secret key from Firestore keys collection"),
    device: str = Query(..., description="Device name")
):
    """
    WebSocket endpoint para streaming de pantalla en tiempo real
    
    **Autenticación requerida:**
    
    Query Parameters:
        - token: Firebase ID token del usuario autenticado
        - secretKey: Secret key asociada al usuario en Firestore
        - device: Nombre del dispositivo (debe coincidir con la key en Firestore)
    
    **Flujo de autenticación:**
    1. Se verifica el token de Firebase Auth
    2. Se extrae el user_id del token
    3. Se busca en Firestore una key que coincida con: user_id, secretKey y device
    4. Si todo es válido, se establece la conexión WebSocket
    
    **Uso desde el cliente:**
    ```javascript
    const ws = new WebSocket(
        `ws://localhost:8000/ws/stream?token=<firebase_token>&secretKey=<secret>&device=<device_name>`
    );
    ```
    
    **Protocolo de mensajes:**
    - Cliente puede enviar frames como datos binarios o JSON
    - Servidor responde con confirmaciones o errores
    - Frames esperados: ~15 FPS (cada 66ms aprox)
    
    **Ejemplo de uso (Python cliente):**
    ```python
    import websockets
    import asyncio
    
    async def stream_screen():
        uri = f"ws://localhost:8000/ws/stream?token={token}&secretKey={key}&device={device}"
        async with websockets.connect(uri) as websocket:
            # Enviar frames
            await websocket.send(frame_data)
            response = await websocket.recv()
    ```
    """
    
    print("\n" + "="*60)
    print("🌐 Nueva solicitud de conexión WebSocket")
    print(f"📱 Device: {device}")
    print(f"🔑 SecretKey (primeros 20 chars): {secretKey[:20] if len(secretKey) > 20 else secretKey}")
    print(f"🎫 Token (primeros 50 chars): {token[:50] if len(token) > 50 else token}...")
    
    # ==========================================
    # PASO 1: Verificar token de Firebase Auth
    # ==========================================
    user_data = await verify_auth_token(token)
    
    if not user_data:
        print("❌ Autenticación fallida: Token inválido")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return
    
    user_id: str = user_data.get('uid')  # type: ignore
    if not user_id:
        print("❌ No se pudo obtener el user_id del token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User ID no disponible")
        return
    
    user_email = user_data.get('email', 'N/A')
    
    print(f"✅ Usuario autenticado: {user_id}")
    print(f"📧 Email: {user_email}")
    
    # ==========================================
    # PASO 2: Verificar secretKey y device en Firestore
    # ==========================================
    is_key_valid = await verify_secret_key(user_id, secretKey, device)
    
    if not is_key_valid:
        print("❌ Validación fallida: Secret key o device no válidos")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, 
            reason="Secret key o device inválidos"
        )
        return
    
    print(f"✅ Secret key y device validados correctamente")
    print("="*60 + "\n")
    
    # ==========================================
    # PASO 3: Establecer conexión WebSocket
    # ==========================================
    await manager.connect(websocket, user_id, device)
    
    # Enviar mensaje de bienvenida
    welcome_msg = {
        "type": "connection_established",
        "message": "Conexión establecida exitosamente",
        "user_id": user_id,
        "device": device,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_personal_message(json.dumps(welcome_msg), websocket)
    
    # ==========================================
    # PASO 4: Mantener la conexión y recibir frames
    # ==========================================
    frame_count = 0
    
    try:
        while True:
            # Recibir datos (puede ser texto o binario)
            # Para frames de imagen, usar receive_bytes() es más eficiente
            try:
                # Intentar recibir como bytes (para imágenes)
                data = await websocket.receive_bytes()
                frame_count += 1
                
                print(f"📸 Frame {frame_count} recibido | Tamaño: {len(data)} bytes | User: {user_id} | Device: {device}")
                
                # Aquí puedes procesar el frame:
                # - Guardarlo en Storage
                # - Reenviar a otros clientes (broadcast)
                # - Procesamiento de imagen
                # - etc.
                
                # Enviar confirmación al cliente
                ack_msg = {
                    "type": "frame_ack",
                    "frame_number": frame_count,
                    "received_bytes": len(data),
                    "status": "ok"
                }
                await manager.send_personal_message(json.dumps(ack_msg), websocket)
                
            except Exception as e:
                # Si no es binario, intentar como texto
                try:
                    data = await websocket.receive_text()
                    print(f"📝 Mensaje de texto recibido: {data[:100]}...")
                    
                    # Puedes manejar comandos de control aquí
                    # Por ejemplo: {"command": "pause"}, {"command": "resume"}, etc.
                    
                    response = {
                        "type": "text_ack",
                        "message": "Mensaje recibido",
                        "status": "ok"
                    }
                    await manager.send_personal_message(json.dumps(response), websocket)
                    
                except:
                    print(f"⚠️ Error al recibir datos: {e}")
                    break
    
    except WebSocketDisconnect:
        print(f"🔌 Cliente desconectado: {user_id}:{device}")
        manager.disconnect(user_id, device)
    
    except Exception as e:
        print(f"❌ Error en la conexión WebSocket: {e}")
        manager.disconnect(user_id, device)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Error interno del servidor")


# ==========================================
# Endpoint de estado (opcional)
# ==========================================

@router.get("/status")
async def websocket_status():
    """
    Obtiene el estado actual de las conexiones WebSocket
    
    Returns:
        dict: Información sobre conexiones activas
    """
    return {
        "active_connections": len(manager.active_connections),
        "connections": list(manager.active_connections.keys())
    }
