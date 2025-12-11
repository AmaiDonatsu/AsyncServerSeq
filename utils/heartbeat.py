"""
WebSocket Heartbeat/Keepalive system
Ensures connections stay alive and detects dead connections
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
import json
from config.logger_config import get_logger

logger = get_logger(__name__)

# Configuration
PING_INTERVAL = 15
PONG_TIMEOUT = 30 
MAX_MISSED_PONGS = 2

class HeartbeatManager:
    """
    Manages heartbeat/keepalive for WebSocket connections
    
    Features:
    - Automatic ping/pong
    - Dead connection detection
    - Connection health tracking
    - Automatic cleanup
    """
    
    def __init__(
        self,
        ping_interval: int = PING_INTERVAL,
        pong_timeout: int = PONG_TIMEOUT,
        max_missed_pongs: int = MAX_MISSED_PONGS
    ):
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.max_missed_pongs = max_missed_pongs
        
        # Track connection health
        # connection_id -> {
        #   'last_ping': datetime,
        #   'last_pong': datetime,
        #   'missed_pongs': int,
        #   'task': asyncio.Task,
        #   'is_alive': bool
        # }
        self.connections: Dict[str, dict] = {}
        
        # Callbacks for connection events
        self.on_connection_dead: Optional[Callable] = None
        
        logger.info("heartbeat.manager_initialized",
                   ping_interval=ping_interval,
                   pong_timeout=pong_timeout,
                   max_missed_pongs=max_missed_pongs)
    
    async def start_heartbeat(
        self,
        connection_id: str,
        websocket: WebSocket,
        on_dead: Optional[Callable] = None
    ):
        """
        Start heartbeat monitoring for a connection
        
        Args:
            connection_id: Unique identifier for the connection
            websocket: WebSocket instance
            on_dead: Callback function when connection is detected as dead
        """
        
        if connection_id in self.connections:
            logger.warning("heartbeat.already_monitoring",
                         connection_id=connection_id)
            return
        
        now = datetime.now()
        
        # Initialize connection tracking
        self.connections[connection_id] = {
            'last_ping': now,
            'last_pong': now,
            'missed_pongs': 0,
            'task': None,
            'is_alive': True,
            'websocket': websocket
        }
        
        # Start heartbeat task
        task = asyncio.create_task(
            self._heartbeat_loop(connection_id, websocket, on_dead)
        )
        self.connections[connection_id]['task'] = task
        
        logger.info("heartbeat.started",
                   connection_id=connection_id)
    
    async def _heartbeat_loop(
        self,
        connection_id: str,
        websocket: WebSocket,
        on_dead: Optional[Callable]
    ):
        """
        Main heartbeat loop - runs continuously for each connection
        """
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                
                # Check if connection still exists
                if connection_id not in self.connections:
                    logger.debug("heartbeat.connection_removed",
                               connection_id=connection_id)
                    break
                
                conn_info = self.connections[connection_id]
                
                # Check if websocket is still connected
                if websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning("heartbeat.websocket_not_connected",
                                 connection_id=connection_id,
                                 state=str(websocket.client_state))
                    await self._handle_dead_connection(connection_id, on_dead)
                    break
                
                # Send ping
                try:
                    ping_msg = {
                        "type": "ping",
                        "timestamp": datetime.now().isoformat(),
                        "sequence": conn_info['missed_pongs']
                    }
                    
                    await websocket.send_text(json.dumps(ping_msg))
                    conn_info['last_ping'] = datetime.now()
                    
                    logger.debug("heartbeat.ping_sent",
                               connection_id=connection_id,
                               missed_pongs=conn_info['missed_pongs'])
                
                except Exception as e:
                    logger.error("heartbeat.ping_failed",
                               connection_id=connection_id,
                               error=str(e))
                    await self._handle_dead_connection(connection_id, on_dead)
                    break
                
                # Check for pong timeout
                time_since_pong = datetime.now() - conn_info['last_pong']
                
                if time_since_pong.total_seconds() > self.pong_timeout:
                    conn_info['missed_pongs'] += 1
                    
                    logger.warning("heartbeat.pong_timeout",
                                 connection_id=connection_id,
                                 missed_pongs=conn_info['missed_pongs'],
                                 time_since_pong_sec=time_since_pong.total_seconds())
                    
                    if conn_info['missed_pongs'] >= self.max_missed_pongs:
                        logger.error("heartbeat.max_missed_pongs",
                                   connection_id=connection_id,
                                   missed_pongs=conn_info['missed_pongs'])
                        await self._handle_dead_connection(connection_id, on_dead)
                        break
        
        except asyncio.CancelledError:
            logger.debug("heartbeat.task_cancelled",
                       connection_id=connection_id)
        
        except Exception as e:
            logger.error("heartbeat.loop_error",
                       connection_id=connection_id,
                       error=str(e),
                       exc_info=True)
    
    async def _handle_dead_connection(
        self,
        connection_id: str,
        on_dead: Optional[Callable]
    ):
        """
        Handle a dead connection
        """
        if connection_id not in self.connections:
            return
        
        conn_info = self.connections[connection_id]
        conn_info['is_alive'] = False
        
        logger.error("heartbeat.connection_dead",
                   connection_id=connection_id,
                   missed_pongs=conn_info['missed_pongs'])
        
        # Call callback if provided
        if on_dead:
            try:
                if asyncio.iscoroutinefunction(on_dead):
                    await on_dead(connection_id)
                else:
                    on_dead(connection_id)
            except Exception as e:
                logger.error("heartbeat.callback_failed",
                           connection_id=connection_id,
                           error=str(e))
        
        # Try to close the websocket gracefully
        try:
            websocket = conn_info.get('websocket')
            if websocket and websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1001, reason="Heartbeat timeout")
        except Exception as e:
            logger.debug("heartbeat.close_failed",
                       connection_id=connection_id,
                       error=str(e))
    
    def record_pong(self, connection_id: str):
        """
        Record that a pong was received from a connection
        
        Args:
            connection_id: Connection identifier
        """
        if connection_id not in self.connections:
            logger.warning("heartbeat.pong_for_unknown_connection",
                         connection_id=connection_id)
            return
        
        conn_info = self.connections[connection_id]
        conn_info['last_pong'] = datetime.now()
        conn_info['missed_pongs'] = 0  # Reset counter
        
        logger.debug("heartbeat.pong_received",
                   connection_id=connection_id)
    
    def stop_heartbeat(self, connection_id: str):
        """
        Stop heartbeat monitoring for a connection
        
        Args:
            connection_id: Connection identifier
        """
        if connection_id not in self.connections:
            return
        
        conn_info = self.connections[connection_id]
        
        # Cancel the heartbeat task
        if conn_info['task'] and not conn_info['task'].done():
            conn_info['task'].cancel()
        
        # Remove from tracking
        del self.connections[connection_id]
        
        logger.info("heartbeat.stopped",
                   connection_id=connection_id)
    
    def is_alive(self, connection_id: str) -> bool:
        """
        Check if a connection is considered alive
        
        Args:
            connection_id: Connection identifier
        
        Returns:
            True if connection is alive, False otherwise
        """
        if connection_id not in self.connections:
            return False
        
        return self.connections[connection_id]['is_alive']
    
    def get_health_info(self, connection_id: str) -> Optional[dict]:
        """
        Get health information for a connection
        
        Args:
            connection_id: Connection identifier
        
        Returns:
            Dictionary with health info or None if connection not found
        """
        if connection_id not in self.connections:
            return None
        
        conn_info = self.connections[connection_id]
        now = datetime.now()
        
        return {
            'connection_id': connection_id,
            'is_alive': conn_info['is_alive'],
            'missed_pongs': conn_info['missed_pongs'],
            'last_ping': conn_info['last_ping'].isoformat(),
            'last_pong': conn_info['last_pong'].isoformat(),
            'seconds_since_ping': (now - conn_info['last_ping']).total_seconds(),
            'seconds_since_pong': (now - conn_info['last_pong']).total_seconds()
        }
    
    def get_all_connections_health(self) -> list:
        """
        Get health info for all tracked connections
        
        Returns:
            List of health info dictionaries
        """
        return [
            self.get_health_info(conn_id)
            for conn_id in self.connections.keys()
        ]
    
    async def cleanup_dead_connections(self):
        """
        Remove all dead connections from tracking
        """
        dead_connections = [
            conn_id
            for conn_id, info in self.connections.items()
            if not info['is_alive']
        ]
        
        for conn_id in dead_connections:
            self.stop_heartbeat(conn_id)
        
        if dead_connections:
            logger.info("heartbeat.cleanup_completed",
                       removed_count=len(dead_connections))
    
    async def shutdown(self):
        """
        Shutdown the heartbeat manager and cancel all tasks
        """
        logger.info("heartbeat.shutting_down",
                   active_connections=len(self.connections))
        
        # Cancel all tasks
        for conn_id in list(self.connections.keys()):
            self.stop_heartbeat(conn_id)
        
        logger.info("heartbeat.shutdown_complete")


# Global heartbeat manager instance
heartbeat_manager = HeartbeatManager()