"""
Rate limiting configuration using SlowAPI
Protects HTTP endpoints from abuse
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import asyncio

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # Default: 100 requests per minute
    storage_uri=os.getenv("REDIS_URL", "memory://"),  # Use Redis in production
    strategy="fixed-window"  # fixed-window o moving-window
)

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom response when rate limit is exceeded
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Try again in {exc.detail}",
            "retry_after": exc.detail
        },
        headers={
            "Retry-After": str(exc.detail)
        }
    )

# Rate limit tiers based on endpoint sensitivity
RATE_LIMITS = {
    "auth": "10/minute",           # Login/auth endpoints
    "upload": "20/minute",          # File uploads
    "download": "50/minute",        # Downloads
    "websocket": "5/minute",        # WebSocket connection attempts
    "standard": "100/minute",       # Standard API calls
    "burst": "300/hour"            # Burst allowance
}

"""
WebSocket-specific rate limiting
Tracks connection attempts per IP
"""

class WebSocketRateLimiter:
    """
    Rate limiter specifically for WebSocket connections
    Prevents connection spam attacks
    """
    
    def __init__(
        self,
        max_connections_per_ip: int = 5,
        max_attempts_per_minute: int = 10,
        cleanup_interval: int = 300  # 5 minutes
    ):
        self.max_connections_per_ip = max_connections_per_ip
        self.max_attempts_per_minute = max_attempts_per_minute
        
        # Track: IP -> (connection_count, last_attempt_time, attempt_count)
        self.connections: Dict[str, Tuple[int, datetime, int]] = defaultdict(
            lambda: (0, datetime.now(), 0)
        )
        
        asyncio.create_task(self._cleanup_task(cleanup_interval))
    
    async def can_connect(self, client_ip: str) -> Tuple[bool, str]:
        """
        Check if an IP can establish a new WebSocket connection
        
        Returns:
            (can_connect: bool, reason: str)
        """
        now = datetime.now()
        
        if client_ip not in self.connections:
            self.connections[client_ip] = (0, now, 1)
            return True, "OK"
        
        conn_count, last_attempt, attempt_count = self.connections[client_ip]
        
        # Check connection limit
        if conn_count >= self.max_connections_per_ip:
            return False, f"Too many concurrent connections from this IP (max: {self.max_connections_per_ip})"
        
        #  attempt limit
        time_since_last = (now - last_attempt).total_seconds()
        
        if time_since_last < 60:
            if attempt_count >= self.max_attempts_per_minute:
                return False, f"Too many connection attempts (max: {self.max_attempts_per_minute}/min)"
            
            self.connections[client_ip] = (conn_count, last_attempt, attempt_count + 1)
        else:
            self.connections[client_ip] = (conn_count, now, 1)
        
        return True, "OK"
    
    def register_connection(self, client_ip: str):
        """Register a successful connection"""
        conn_count, last_attempt, attempt_count = self.connections[client_ip]
        self.connections[client_ip] = (conn_count + 1, last_attempt, attempt_count)
        print(f"📊 Registered connection from {client_ip} (total: {conn_count + 1})")
    
    def unregister_connection(self, client_ip: str):
        """Unregister a disconnected connection"""
        if client_ip not in self.connections:
            return
        
        conn_count, last_attempt, attempt_count = self.connections[client_ip]
        new_count = max(0, conn_count - 1)
        self.connections[client_ip] = (new_count, last_attempt, attempt_count)
        print(f"📊 Unregistered connection from {client_ip} (remaining: {new_count})")
    
    async def _cleanup_task(self, interval: int):
        """Periodically clean up old entries"""
        while True:
            await asyncio.sleep(interval)
            now = datetime.now()
            
            to_remove = []
            for ip, (conn_count, last_attempt, _) in self.connections.items():
                if conn_count == 0 and (now - last_attempt).total_seconds() > 300:
                    to_remove.append(ip)
            
            for ip in to_remove:
                del self.connections[ip]
            
            if to_remove:
                print(f"🧹 Cleaned up {len(to_remove)} stale IP entries")

ws_rate_limiter = WebSocketRateLimiter()