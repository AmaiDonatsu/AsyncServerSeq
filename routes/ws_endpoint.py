"""
WebSocket endpoint for real-time screen streaming
Handles authentication and device validation for mobile screen capture streaming
"""

import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState
from typing import Optional
from config.firebase_config import FirebaseConfig
from firebase_admin import auth
import json
import asyncio

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

router = APIRouter(prefix="/ws", tags=["WebSocket"])



# Auxiliary authentication functions
# ==========================================

async def verify_auth_token(token: str) -> Optional[dict]:
    """
    Verrifys the Firebase Auth token
    
    Args:
        token: Firebase ID token
    
    Returns:
        dict with user info if valid, None if not valid
    """
    try:
        decoded_token = FirebaseConfig.verify_token(token)
        return decoded_token
    except Exception as e:
        print(f"❌ Error al verificar token: {e}")
        return None


async def verify_secret_key(user_id: str, secret_key: str, device: str) -> bool:
    """
    Verifica que la secret key y el device existen en Firestore para el usuario dado
    
    Args:
        user_id: user ID
        secret_key: secret key sent in the request
        device: device name

    Returns:
        True if the key exists and belongs to the user, False otherwise
    """
    try:
        db = FirebaseConfig.get_firestore()
        keys_ref = db.collection('keys')
        
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


# WebSocket Connection Manager
# ==========================================

class ConnectionManager:
    """
    Manages active WebSocket connections
    Separates between streamers (who send) and viewers (who receive)
    """
    def __init__(self):
        # Conexiones que transmiten (streamers)
        self.streamers: dict[str, WebSocket] = {}
        
        # Conexiones que visualizan (viewers)
        # Clave: "user_id:device" -> Lista de WebSockets que están viendo ese stream
        self.viewers: dict[str, list[WebSocket]] = {}
    
    async def connect_streamer(self, websocket: WebSocket, user_id: str, device: str):
        """
        Acepta y registra una nueva conexión de streaming (transmisión)
        """
        await websocket.accept()
        connection_id = f"{user_id}:{device}"
        self.streamers[connection_id] = websocket
        print(f"🎥 Nuevo streamer: {connection_id}")
        print(f"📊 Streamers activos: {len(self.streamers)} | Viewers activos: {sum(len(v) for v in self.viewers.values())}")
    
    async def connect_viewer(self, websocket: WebSocket, user_id: str, device: str):
        """
        Acepta y registra una nueva conexión de visualización (viewer)
        """
        await websocket.accept()
        connection_id = f"{user_id}:{device}"
        
        if connection_id not in self.viewers:
            self.viewers[connection_id] = []
        
        self.viewers[connection_id].append(websocket)
        print(f"👁️ Nuevo viewer para: {connection_id}")
        print(f"🔍 Total de viewers para este stream: {len(self.viewers[connection_id])}")
        print(f"🔍 WebSocket state: {websocket.client_state}")
        print(f"📊 Streamers activos: {len(self.streamers)} | Viewers activos: {sum(len(v) for v in self.viewers.values())}")
    
    def disconnect_streamer(self, user_id: str, device: str):
        """
        Elimina una conexión de streamer del registro
        """
        connection_id = f"{user_id}:{device}"
        if connection_id in self.streamers:
            del self.streamers[connection_id]
            print(f"🎥 Streamer desconectado: {connection_id}")
            print(f"📊 Streamers activos: {len(self.streamers)} | Viewers activos: {sum(len(v) for v in self.viewers.values())}")
    
    def disconnect_viewer(self, user_id: str, device: str, websocket: WebSocket):
        """
        Elimina una conexión de viewer del registro
        """
        connection_id = f"{user_id}:{device}"
        if connection_id in self.viewers:
            if websocket in self.viewers[connection_id]:
                self.viewers[connection_id].remove(websocket)
                print(f"�️ Viewer desconectado de: {connection_id}")
                
                # Si no quedan viewers para este stream, limpiar la lista
                if len(self.viewers[connection_id]) == 0:
                    del self.viewers[connection_id]
            
            print(f"📊 Streamers activos: {len(self.streamers)} | Viewers activos: {sum(len(v) for v in self.viewers.values())}")
    
    def is_stream_active(self, user_id: str, device: str) -> bool:
        connection_id = f"{user_id}:{device}"
        return connection_id in self.streamers
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """
        Sends a text message to a specific connection
        """
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)
    
    async def send_personal_bytes(self, data: bytes, websocket: WebSocket):
        """
        Sends binary data to a specific connection
        """
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_bytes(data)
    
    async def broadcast_frame_to_viewers(self, user_id: str, device: str, frame_data: bytes):
        """
        Sends a frame to all viewers connected to that specific stream
        """
        connection_id = f"{user_id}:{device}"
        
        print(f"🔍 Buscando viewers para: {connection_id}")
        print(f"🔍 Viewers registrados: {list(self.viewers.keys())}")
        
        if connection_id not in self.viewers:
            print(f"⚠️ No hay viewers para este stream")
            return

        print(f"📤 Enviando frame de {len(frame_data)} bytes a {len(self.viewers[connection_id])} viewers")

        # Send the frame to all viewers
        disconnected_viewers = []
        
        for idx, viewer_ws in enumerate(self.viewers[connection_id]):
            try:
                print(f"  → Viewer {idx+1}: enviando (estado: {viewer_ws.client_state})")
                if viewer_ws.client_state == WebSocketState.CONNECTED:
                    await viewer_ws.send_bytes(frame_data)
                    print(f"  ✅ Enviado exitosamente a viewer {idx+1}")
                else:
                    print(f"  ⚠️ Viewer {idx+1} no conectado")
                    disconnected_viewers.append(viewer_ws)
            except Exception as e:
                print(f"  ❌ Error enviando a viewer {idx+1}: {e}")
                disconnected_viewers.append(viewer_ws)
        
        # Limpiar viewers desconectados
        for viewer_ws in disconnected_viewers:
            if viewer_ws in self.viewers[connection_id]:
                self.viewers[connection_id].remove(viewer_ws)
    
    async def broadcast(self, message: str):
        """
        Sends a text message to all connected streamers and viewers
        """
        # Send to streamers
        for connection in self.streamers.values():
            if connection.client_state == WebSocketState.CONNECTED:
                await connection.send_text(message)

        # Send to viewers
        for viewer_list in self.viewers.values():
            for viewer_ws in viewer_list:
                if viewer_ws.client_state == WebSocketState.CONNECTED:
                    await viewer_ws.send_text(message)
                    
    async def send_command_to_streamer(self, user_id: str, device: str, command: str):
        """
        Sends a text command to the specific streamer (the device)
        """
        connection_id = f"{user_id}:{device}"
        
        if connection_id not in self.streamers:
            print(f"⚠️ No active streamer for: {connection_id}")
            return False
        
        streamer_ws = self.streamers[connection_id]
        
        if streamer_ws.client_state == WebSocketState.CONNECTED:
            print(f"📤 Enviando comando al streamer: {connection_id}")
            await streamer_ws.send_text(command)
            return True
        else:
            print(f"⚠️ Streamer not connected: {connection_id}")
            return False


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
    WebSocket endpoint for real-time screen streaming

    **Authentication required:**

    Query Parameters:
        - token: Firebase ID token of the authenticated user
        - secretKey: Secret key associated with the key in Firestore
        - device: Device name (must match the key in Firestore)

    **Authentication flow:**
    1. Verify the Firebase Auth token
    2. Extract the user_id from the token
    3. Look up a key in Firestore that matches: user_id, secretKey, and device
    4. If everything is valid, establish the WebSocket connection for streaming

    **Message Protocol:**
    - Client can send frames as binary data or JSON
    - Server responds with confirmations or errors
    - Expected frame rate: ~15 FPS (every 66ms approx)
    """
    
    print("\n" + "="*60)
    print("🌐 New WebSocket connection")
    print(f"📱 Device: {device}")
    print(f"🔑 SecretKey (first 20 chars): {secretKey[:20] if len(secretKey) > 20 else secretKey}")
    print(f"🎫 Token (first 50 chars): {token[:50] if len(token) > 50 else token}...")

    # Verify Firebase Auth token
    # ==========================================
    user_data = await verify_auth_token(token)
    
    if not user_data:
        print("❌ Authentication failed: Invalid token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
    
    user_id: str = user_data.get('uid')  # type: ignore
    if not user_id:
        print("❌ No se pudo obtener el user_id del token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User ID no disponible")
        return
    
    user_email = user_data.get('email', 'N/A')
    
    print(f"✅ Usuario autenticado: {user_id}")
    print(f"📧 Email: {user_email}")
    
    # Verify secretKey and device in Firestore
    # ==========================================
    is_key_valid = await verify_secret_key(user_id, secretKey, device)
    
    if not is_key_valid:
        print("❌ Validation failed: Secret key or device not valid")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Secret key or device invalid"
        )
        return

    print(f"✅ Secret key and device validated successfully")
    print("="*60 + "\n")
    
    # Establish WebSocket connection as streamer
    # ==========================================
    await manager.connect_streamer(websocket, user_id, device)

    # Send welcome message
    welcome_msg = {
        "type": "connection_established",
        "message": "Connection established successfully",
        "user_id": user_id,
        "device": device,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_personal_message(json.dumps(welcome_msg), websocket)
    
    # Maintain connection and receive frames
    # ==========================================
    frame_count = 0
    
    try:
        while True:
            # 🆕 USAR receive() genérico que maneja ambos
            message = await websocket.receive()
            
            # 🎯 Detectar el tipo de mensaje
            if "bytes" in message:
                # ==========================================
                # Es un FRAME (binario)
                # ==========================================
                data = message["bytes"]
                frame_count += 1
                
                connection_id = f"{user_id}:{device}"
                viewer_count = len(manager.viewers.get(connection_id, []))
                
                # Log cada 30 frames para no saturar
                if frame_count % 30 == 0:
                    print(f"📸 Frame {frame_count} | {len(data)} bytes | Viewers: {viewer_count}")
                
                # Broadcast a viewers
                await manager.broadcast_frame_to_viewers(user_id, device, data)
                
                # ACK opcional (puedes quitarlo para mejorar performance)
                # ack_msg = {
                #     "type": "frame_ack",
                #     "frame_number": frame_count,
                #     "status": "ok"
                # }
                # await manager.send_personal_message(json.dumps(ack_msg), websocket)
            
            elif "text" in message:
                # ==========================================
                # Es un MENSAJE DE TEXTO (respuesta de comando)
                # ==========================================
                text_data = message["text"]
                print(f"📨 Respuesta del celular: {text_data[:200]}...\n\n")
                
                # Parsear la respuesta
                try:
                    print("iniciando try de json.loads")
                    response_json = json.loads(text_data)
                    response_type = response_json.get("type")
                    print(f"Tipo de respuesta: {response_type}")
                    if response_type == "response":
                        print("es response\n")
                        # Es una respuesta de comando ejecutado
                        command_id = response_json.get("id")
                        status_cmd = response_json.get("status")
                        print(f"✅ Comando {command_id} ejecutado: {status_cmd}")
                        
                        # Opcional: reenviar la respuesta a los viewers
                        connection_id = f"{user_id}:{device}"
                        print(f"🔍 Buscando viewers para reenviar respuesta de comando a: {connection_id}")
                        if DEBUG:
                            print(f"\nViewers: {manager.viewers}")
                            print(f" connection_id in viewers: {connection_id in manager.viewers}\n")

                        if connection_id in manager.viewers:
                            print(f"📤 Reenviando respuesta de comando a {len(manager.viewers[connection_id])} viewers")
                            for viewer_ws in manager.viewers[connection_id]:
                                if viewer_ws.client_state == WebSocketState.CONNECTED:
                                    await viewer_ws.send_text(text_data)
                    elif response_type == "ui_data":
                        connection_id = f"{user_id}:{device}"
                        if DEBUG:
                            print("es ui_data\n")
                        
                        if connection_id in manager.viewers:
                            print(f"📤 Reenviando UI data a {len(manager.viewers[connection_id])} viewers")
                            for viewer_ws in manager.viewers[connection_id]:
                                if viewer_ws.client_state == WebSocketState.CONNECTED:
                                    await viewer_ws.send_text(text_data)
                
                except json.JSONDecodeError:
                    print(f"⚠️ Mensaje no es JSON válido: {text_data[:100]}")
            elif "type" in message and message["type"] == "ui_data":
                print(f"🖥️ UI data received: {message['data'][:100]}...")
                response_json = json.loads(message["hierarchy"])

                try:
                    await manager.send_personal_message(json.dumps(message), websocket=websocket)
                except Exception as e:
                    print(f"❌ Error parseando UI data: {e}")


    except WebSocketDisconnect:
        print(f"🔌 Streamer desconectado: {user_id}:{device}")
        manager.disconnect_streamer(user_id, device)

    except Exception as e:
        print(f"❌ Error en la conexión WebSocket: {e}")
        import traceback
        traceback.print_exc()
        manager.disconnect_streamer(user_id, device)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Error interno del servidor")


# ==========================================
# Endpoint WebSocket for Viewers
# ==========================================

@router.websocket("/view")
async def websocket_view_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Firebase Auth ID token"),
    secretKey: str = Query(..., description="Secret key from Firestore keys collection"),
    device: str = Query(..., description="Device name del stream a visualizar")
):
    """
    WebSocket endpoint for viewing a real-time screen stream

    **Auth required:**

    Query Parameters:
        - token: Firebase ID token of the authenticated user
        - secretKey: SecretKey generated and stored in Firestore 
        - device: device name to view

    **Requirements:**
    1. The user must be authenticated (valid token)
    2. The secretKey and device must exist in Firestore for that user
    3. There must be an active stream for that device (someone transmitting)

    **Flow:**
    1. The Firebase Auth token is validated
    2. The secretKey + device are validated in Firestore
    3. It is verified that there is an active stream for that device
    4. If everything is valid, the viewer receives the frames in real-time
    
    
    """
    
    print("\n" + "="*60)
    print("👁️ New visualization request")
    print(f"📱 Device to visualize: {device}")
    print(f"🔑 SecretKey (first 20 chars): {secretKey[:20] if len(secretKey) > 20 else secretKey}")
    print(f"🎫 Token (first 50 chars): {token[:50] if len(token) > 50 else token}...")

    # Token Authentication
    ###############

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
    
    
    # Veryfy secretKey and device
    # ==========================================
    is_key_valid = await verify_secret_key(user_id, secretKey, device)
    
    if not is_key_valid:
        print("❌ Validación fallida: Secret key o device no válidos")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, 
            reason="Secret key o device inválidos"
        )
        return
    
    # Active stream verification
    # ==========================================
    if not manager.is_stream_active(user_id, device):
        print(f"❌ No hay stream activo para: {user_id}:{device}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="No hay stream activo para este dispositivo"
        )
        return
    
    print(f"✅ Stream activo encontrado para: {user_id}:{device}")
    print("="*60 + "\n")
    
    # Connect as viewer
    # ==========================================
    await manager.connect_viewer(websocket, user_id, device)
    
    welcome_msg = {
        "type": "viewer_connected",
        "message": "Conectado al stream exitosamente",
        "user_id": user_id,
        "device": device,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_personal_message(json.dumps(welcome_msg), websocket)
     
    # connection established
    try:
        while True:
            try:
                # Recive commands from viewer
                data = await websocket.receive_text()
                print(f"📝 Comando del viewer: {data[:100]}...")
                
                try:
                    command_data = json.loads(data)
                    command_type = command_data.get("type")
                    
                        # 🎯 if is a device command
                    if command_type == "command":
                        print(f"🎮 Reenviando comando al dispositivo: {user_id}:{device}")
                        
                        # send command to streamer
                        await manager.send_command_to_streamer(user_id, device, data)
                        
                        # ACK to viewer
                        response = {
                            "type": "command_ack",
                            "message": "Command sent to device",
                            "status": "ok"
                        }
                        await manager.send_personal_message(json.dumps(response), websocket)
                    
                    else:
                        # Other commands (request_keyframe, etc.)
                        response = {
                            "type": "command_ack",
                            "message": "Command received",
                            "status": "ok"
                        }
                        await manager.send_personal_message(json.dumps(response), websocket)
                
                except json.JSONDecodeError:
                    print(f"⚠️ Error parseando JSON: {data}")
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"⚠️ Error en viewer: {e}")
                break
    
    except WebSocketDisconnect:
        print(f"👁️ Viewer desconectado de: {user_id}:{device}")
        manager.disconnect_viewer(user_id, device, websocket)
    
    except Exception as e:
        print(f"❌ Error en la conexión del viewer: {e}")
        manager.disconnect_viewer(user_id, device, websocket)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Error interno del servidor")

@router.get("/status")
async def websocket_status():
    """
    Obtiene el estado actual de las conexiones WebSocket
    
    Returns:
        dict: Información sobre conexiones activas (streamers y viewers)
    """
    streamers = list(manager.streamers.keys())
    
    viewers_info = {}
    for stream_id, viewer_list in manager.viewers.items():
        viewers_info[stream_id] = len(viewer_list)
    
    return {
        "streamers": {
            "count": len(streamers),
            "active": streamers
        },
        "viewers": {
            "total_count": sum(len(v) for v in manager.viewers.values()),
            "by_stream": viewers_info
        }
    }
