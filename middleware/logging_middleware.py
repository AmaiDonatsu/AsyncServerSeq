"""
Logging middleware for FastAPI
Automatically logs all HTTP requests and responses
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from config.logger_config import get_logger, bind_request_context, clear_request_context, generate_request_id

logger = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests and responses
    Adds request_id to context for tracing
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = generate_request_id()
        
        # Bind context
        bind_request_context(request_id=request_id)
        
        # Extract request info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        
        # Log request
        logger.info(
            "http.request_started",
            method=method,
            path=path,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent", "unknown"),
            query_params=dict(request.query_params) if request.query_params else None
        )
        
        # Measure time
        start_time = time.perf_counter()
        
        try:
            # Process request
            response: Response = await call_next(request)
            
            # Calculate duration
            duration = (time.perf_counter() - start_time) * 1000  # ms
            
            # Log response
            logger.info(
                "http.request_completed",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration, 2)
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                "http.request_failed",
                method=method,
                path=path,
                duration_ms=round(duration, 2),
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True
            )
            
            raise
        
        finally:
            # Clear context
            clear_request_context()