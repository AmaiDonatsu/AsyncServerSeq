"""
WebSocket endpoint for real-time screen streaming
Handles authentication and device validation for mobile screen capture streaming
"""

import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState
from typing import Optional
from config.firebase_config import FirebaseConfig
from config.logger_config import get_logger, bind_request_context, clear_request_context, LogEvent, generate_request_id
from firebase_admin import auth
import json
import asyncio

from config.rate_limiter import ws_rate_limiter
from utils.frame_validator import frame_validator, MAX_FRAME_SIZE

logger = get_logger(__name__)

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
        logger.warning(LogEvent.AUTH_TOKEN_FAILED, error=str(e))
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
            logger.info(LogEvent.AUTH_KEY_VALIDATED, 
                       user_id=user_id, 
                       device=device)
            return True
        else:
            logger.warning(LogEvent.AUTH_KEY_INVALID, 
                          user_id=user_id, 
                          device=device)
            return False
            
    except Exception as e:
        logger.error("auth.key_check_failed", 
                    user_id=user_id,
                    device=device,
                    error=str(e),
                    exc_info=True)
        return False


# WebSocket Connection Manager
# ==========================================

class ConnectionManager:
    """
    Manages active WebSocket connections
    Separates between streamers (who send) and viewers (who receive)
    """
    def __init__(self):
        self.streamers: dict[str, WebSocket] = {}
        self.viewers: dict[str, list[WebSocket]] = {}
        self.logger = get_logger(f"{__name__}.ConnectionManager")

    async def connect_streamer(self, websocket: WebSocket, user_id: str, device: str):
        """
        Acepta y registra una nueva conexión de streaming (transmisión)
        """
        await websocket.accept()
        connection_id = f"{user_id}:{device}"
        self.streamers[connection_id] = websocket
        
        self.logger.info(LogEvent.WS_CONNECTION_ESTABLISHED,
                        connection_type="streamer",
                        connection_id=connection_id,
                        total_streamers=len(self.streamers),
                        total_viewers=sum(len(v) for v in self.viewers.values()))
        
    async def connect_viewer(self, websocket: WebSocket, user_id: str, device: str):
        """
        Acepta y registra una nueva conexión de visualización (viewer)
        """
        await websocket.accept()
        connection_id = f"{user_id}:{device}"
        
        if connection_id not in self.viewers:
            self.viewers[connection_id] = []
        
        self.viewers[connection_id].append(websocket)
        self.logger.info(LogEvent.WS_CONNECTION_ESTABLISHED,
                        connection_type="viewer",
                        connection_id=connection_id,
                        viewers_for_stream=len(self.viewers[connection_id]),
                        total_streamers=len(self.streamers))
    
    def disconnect_streamer(self, user_id: str, device: str):
        """
        Elimina una conexión de streamer del registro
        """
        connection_id = f"{user_id}:{device}"
        if connection_id in self.streamers:
            del self.streamers[connection_id]

            self.logger.info(LogEvent.WS_DISCONNECTED,
                           connection_type="streamer",
                           connection_id=connection_id,
                           remaining_streamers=len(self.streamers))
    
    def disconnect_viewer(self, user_id: str, device: str, websocket: WebSocket):
        """
        Elimina una conexión de viewer del registro
        """
        connection_id = f"{user_id}:{device}"
        if connection_id in self.viewers:
            if websocket in self.viewers[connection_id]:
                self.viewers[connection_id].remove(websocket)
                
                self.logger.info(LogEvent.WS_DISCONNECTED,
                               connection_type="viewer",
                               connection_id=connection_id,
                               remaining_viewers=len(self.viewers[connection_id]))
                
                # Si no quedan viewers para este stream, limpiar la lista
                if len(self.viewers[connection_id]) == 0:
                    del self.viewers[connection_id]
            
            self.logger.debug("ws.connection_stats",
                           total_streamers=len(self.streamers),
                           total_viewers=sum(len(v) for v in self.viewers.values()))
    
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
        
        if connection_id not in self.viewers:
            return

        viewer_count = len(self.viewers[connection_id])

        # Send the frame to all viewers
        disconnected_viewers = []
        
        for idx, viewer_ws in enumerate(self.viewers[connection_id]):
            try:
                if viewer_ws.client_state == WebSocketState.CONNECTED:
                    await viewer_ws.send_bytes(frame_data)
                else:
                    disconnected_viewers.append(viewer_ws)
            except Exception as e:
                self.logger.warning("ws.frame_send_error",
                                   connection_id=connection_id,
                                   viewer_index=idx,
                                   error=str(e))
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
            self.logger.warning("ws.no_active_streamer",
                              connection_id=connection_id)
            return False
        
        streamer_ws = self.streamers[connection_id]
        
        if streamer_ws.client_state == WebSocketState.CONNECTED:
            self.logger.debug(LogEvent.WS_COMMAND_SENT,
                            connection_id=connection_id)
            await streamer_ws.send_text(command)
            return True
        else:
            self.logger.warning("ws.streamer_not_connected",
                              connection_id=connection_id)
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

    request_id = generate_request_id()
    client_ip = websocket.client.host if websocket.client else "unknown"
    bind_request_context(request_id=request_id, device=device)

    logger.info(LogEvent.WS_CONNECTION_ATTEMPT,
               connection_type="streamer",
               device=device,
               client_ip=client_ip)

    can_connect, reason = await ws_rate_limiter.can_connect(client_ip)
    if not can_connect:
        logger.warning(LogEvent.RATE_LIMIT_EXCEEDED,
                      client_ip=client_ip,
                      reason=reason,
                      connection_type="streamer")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")
        return
    
    # Verify Firebase Auth token
    # ==========================================
    user_data = await verify_auth_token(token)
    
    if not user_data:
        logger.warning(LogEvent.AUTH_TOKEN_FAILED,
                      device=device,
                      client_ip=client_ip)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
    
    user_id: str = user_data.get('uid')  # type: ignore
    if not user_id:
        logger.warning("auth.user_id_missing",
                      device=device,
                      client_ip=client_ip)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User ID no disponible")
        return
    
    bind_request_context(user_id=user_id)
    user_email = user_data.get('email', 'N/A')
    
    logger.info("auth.user_identified",
               user_id=user_id,
               email=user_email)
    
    # Verify secretKey and device in Firestore
    # ==========================================
    is_key_valid = await verify_secret_key(user_id, secretKey, device)
    
    if not is_key_valid:
        logger.warning(LogEvent.AUTH_KEY_INVALID,
                      user_id=user_id,
                      device=device)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Secret key or device invalid"
        )
        return
    
    # Establish WebSocket connection as streamer
    # ==========================================
    await manager.connect_streamer(websocket, user_id, device)
    ws_rate_limiter.register_connection(client_ip)

    connection_id = f"{user_id}:{device}"

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
    rejected_frames = 0
    try:
        while True:
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            if "bytes" in message:
                data = message["bytes"]

                is_valid, status_msg, validation_msg = frame_validator.validate_frame_size(data)
                
                if not is_valid:
                    rejected_frames += 1
                    logger.warning(LogEvent.WS_FRAME_REJECTED,
                                  connection_id=connection_id,
                                  reason=status_msg,
                                  message=validation_msg,
                                  rejected_count=rejected_frames)

                    error_mmsg = {
                        "type": "frame_rejected",
                        "reason": status_msg,
                        "message": validation_msg,
                        "frame_number": frame_count
                    }
                    await manager.send_personal_message(json.dumps(error_mmsg), websocket)

                    if rejected_frames > 10:
                        logger.error("ws.too_many_rejected_frames",
                                    connection_id=connection_id,
                                    rejected_count=rejected_frames)
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Demasiados frames inválidos")
                        break
                    continue

                rate_ok, rate_msg = frame_validator.validate_frame_rate(connection_id)
                if not rate_ok:
                    if frame_count % 100 == 0:
                        logger.debug("ws.frame_rate_throttled",
                                    connection_id=connection_id,
                                    message=rate_msg)
                    continue
                #connection_id = f"{user_id}:{device}"

                frame_validator.record_frame(connection_id, len(data))

                frame_count += 1
                #viewer_count = len(manager.viewers.get(connection_id, []))
                
                # Log cada 30 frames para no saturar
                if frame_count % 30 == 0:
                    stats = frame_validator.get_stats(connection_id)
                    logger.debug(LogEvent.WS_FRAME_RECEIVED,
                                connection_id=connection_id,
                                frame_number=frame_count,
                                frame_size_kb=round(len(data)/1024, 1),
                                avg_fps=stats.get('avg_fps', 0),
                                bandwidth_mbps=stats.get('bandwidth_mbps', 0))
                    
                # Broadcast a viewers
                await manager.broadcast_frame_to_viewers(user_id, device, data)
                
               
            elif "text" in message:
                # ==========================================
                # Es un MENSAJE DE TEXTO (respuesta de comando)
                # ==========================================
                text_data = message["text"]
                logger.debug(LogEvent.WS_COMMAND_RECEIVED,
                            connection_id=connection_id,
                            message_preview=text_data[:200])
                
                # Parsear la respuesta
                try:
                    response_json = json.loads(text_data)
                    response_type = response_json.get("type")
                    
                    if response_type == "response":
                        command_id = response_json.get("id")
                        status_cmd = response_json.get("status")
                        logger.info("ws.command_response",
                                   connection_id=connection_id,
                                   command_id=command_id,
                                   status=status_cmd)
                        
                        if connection_id in manager.viewers:
                            viewer_count = len(manager.viewers[connection_id])
                            logger.debug("ws.forwarding_response",
                                        connection_id=connection_id,
                                        viewer_count=viewer_count)
                            for viewer_ws in manager.viewers[connection_id]:
                                if viewer_ws.client_state == WebSocketState.CONNECTED:
                                    await viewer_ws.send_text(text_data)
                    elif response_type == "ui_data":
                        if connection_id in manager.viewers:
                            viewer_count = len(manager.viewers[connection_id])
                            logger.debug("ws.forwarding_ui_data",
                                        connection_id=connection_id,
                                        viewer_count=viewer_count)
                            for viewer_ws in manager.viewers[connection_id]:
                                if viewer_ws.client_state == WebSocketState.CONNECTED:
                                    await viewer_ws.send_text(text_data)
                
                except json.JSONDecodeError:
                    logger.warning("ws.invalid_json",
                                  connection_id=connection_id,
                                  message_preview=text_data[:100])
            elif "type" in message and message["type"] == "ui_data":
                logger.debug("ws.ui_data_received",
                            connection_id=connection_id)
                response_json = json.loads(message["hierarchy"])

                try:
                    await manager.send_personal_message(json.dumps(message), websocket=websocket)
                except Exception as e:
                    logger.error("ws.ui_data_error",
                                connection_id=connection_id,
                                error=str(e),
                                exc_info=True)


    except WebSocketDisconnect:
        final_stats = frame_validator.get_stats(connection_id)
        logger.info(LogEvent.WS_DISCONNECTED,
                   connection_type="streamer",
                   connection_id=connection_id,
                   total_frames=final_stats.get('total_frames', 0),
                   avg_fps=final_stats.get('avg_fps', 0),
                   total_data_mb=round(final_stats.get('total_bytes', 0) / (1024*1024), 2),
                   rejected_frames=rejected_frames,
                   duration_seconds=round(final_stats.get('duration_seconds', 0), 2))

    finally:
        manager.disconnect_streamer(user_id, device)
        ws_rate_limiter.unregister_connection(client_ip)
        frame_validator.cleanup_connection(connection_id)
        clear_request_context()


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
    
    request_id = generate_request_id()
    client_ip = websocket.client.host if websocket.client else "unknown"
    bind_request_context(request_id=request_id, device=device)

    logger.info(LogEvent.WS_CONNECTION_ATTEMPT,
               connection_type="viewer",
               device=device,
               client_ip=client_ip)

    # Rate Limiting for Viewers
    can_connect, reason = await ws_rate_limiter.can_connect(client_ip)
    if not can_connect:
        logger.warning(LogEvent.RATE_LIMIT_EXCEEDED,
                      client_ip=client_ip,
                      reason=reason,
                      connection_type="viewer")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")
        return

    # Token Authentication
    ###############

    user_data = await verify_auth_token(token)
    
    if not user_data:
        logger.warning(LogEvent.AUTH_TOKEN_FAILED,
                      device=device,
                      client_ip=client_ip,
                      connection_type="viewer")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
        return
    
    user_id: str = user_data.get('uid')  # type: ignore
    if not user_id:
        logger.warning("auth.user_id_missing",
                      device=device,
                      client_ip=client_ip,
                      connection_type="viewer")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User ID no disponible")
        return
    
    bind_request_context(user_id=user_id)
    user_email = user_data.get('email', 'N/A')
    logger.info("auth.user_identified",
               user_id=user_id,
               email=user_email,
               connection_type="viewer")
    
    
    # Veryfy secretKey and device
    # ==========================================
    is_key_valid = await verify_secret_key(user_id, secretKey, device)
    
    if not is_key_valid:
        logger.warning(LogEvent.AUTH_KEY_INVALID,
                      user_id=user_id,
                      device=device,
                      connection_type="viewer")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, 
            reason="Secret key o device inválidos"
        )
        return
    
    # Active stream verification
    # ==========================================
    if not manager.is_stream_active(user_id, device):
        logger.warning("ws.no_active_stream",
                      user_id=user_id,
                      device=device)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="No hay stream activo para este dispositivo"
        )
        return
    
    logger.info("ws.stream_found",
               user_id=user_id,
               device=device)
    
    # Connect as viewer
    # ==========================================
    await manager.connect_viewer(websocket, user_id, device)
    ws_rate_limiter.register_connection(client_ip)
    
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
                logger.debug(LogEvent.WS_COMMAND_RECEIVED,
                            connection_id=f"{user_id}:{device}",
                            connection_type="viewer",
                            command_preview=data[:100])
                
                try:
                    command_data = json.loads(data)
                    command_type = command_data.get("type")
                    
                        # 🎯 if is a device command
                    if command_type == "command":
                        logger.info(LogEvent.WS_COMMAND_SENT,
                                   connection_id=f"{user_id}:{device}",
                                   command_type=command_type)
                        
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
                    logger.warning("ws.invalid_json",
                                  connection_id=f"{user_id}:{device}",
                                  connection_type="viewer",
                                  data_preview=data[:100])
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("ws.viewer_error",
                            connection_id=f"{user_id}:{device}",
                            error=str(e),
                            exc_info=True)
                break
    
    except WebSocketDisconnect:
        logger.info(LogEvent.WS_DISCONNECTED,
                   connection_type="viewer",
                   connection_id=f"{user_id}:{device}")
        manager.disconnect_viewer(user_id, device, websocket)
        ws_rate_limiter.unregister_connection(client_ip)
        clear_request_context()
    
    except Exception as e:
        logger.error("ws.viewer_connection_error",
                    connection_id=f"{user_id}:{device}",
                    error=str(e),
                    exc_info=True)
        manager.disconnect_viewer(user_id, device, websocket)
        ws_rate_limiter.unregister_connection(client_ip)
        clear_request_context()
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
