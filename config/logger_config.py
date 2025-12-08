"""
Structured logging configuration
Provides consistent, parseable logs across the application
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from typing import Any, Dict
import structlog
from pythonjsonlogger import jsonlogger

# Determine environment
ENV = os.getenv("ENVIRONMENT", "development")  # development, staging, production
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if ENV == "development" else "INFO")

# ==========================================
# Custom processors for structlog
# ==========================================

def add_app_context(logger, method_name, event_dict):
    """Add application-wide context to every log"""
    event_dict["app"] = "AsyncServer"
    event_dict["environment"] = ENV
    event_dict["version"] = "1.0.0"  
    return event_dict

def add_timestamp(logger, method_name, event_dict):
    """Add ISO 8601 timestamp"""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict

def add_log_level(logger, method_name, event_dict):
    """Ensure log level is always present"""
    if "level" not in event_dict:
        event_dict["level"] = method_name.upper()
    return event_dict

def extract_exception_info(logger, method_name, event_dict):
    """Better exception formatting"""
    if "exception" in event_dict:
        exc = event_dict["exception"]
        event_dict["exception_type"] = type(exc).__name__
        event_dict["exception_message"] = str(exc)
        # Keep full traceback for debugging
        import traceback
        event_dict["traceback"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return event_dict

# ==========================================
# Console formatter for development
# ==========================================

class ColoredConsoleRenderer:
    """
    Pretty-print logs for development with colors
    """
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    def __call__(self, logger, method_name, event_dict):
        """Render log entry with colors"""
        level = event_dict.get("level", "INFO").upper()
        timestamp = event_dict.get("timestamp", "")
        event = event_dict.get("event", "log")
        
        # Color for level
        color = self.COLORS.get(level, "")
        
        # Build message
        parts = [
            f"{self.BOLD}{timestamp}{self.RESET}",
            f"{color}[{level}]{self.RESET}",
            f"{self.BOLD}{event}{self.RESET}"
        ]
        
        # Add context fields (exclude metadata)
        exclude_keys = {"timestamp", "level", "event", "app", "environment", "version"}
        context = {k: v for k, v in event_dict.items() if k not in exclude_keys}
        
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            parts.append(f"- {context_str}")
        
        return " ".join(parts) + "\n"

# ==========================================
# JSON formatter for production
# ==========================================

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    JSON formatter for production logs
    Compatible with log aggregation tools
    """
    
    def add_fields(self, log_record, record, message_dict):
        """Customize JSON output"""
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add location info
        log_record['file'] = record.filename
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

# ==========================================
# Configure structlog
# ==========================================

def configure_logging():
    """
    Configure structlog with appropriate processors and renderers
    """
    
    # Shared processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_timestamp,
        add_log_level,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        extract_exception_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    # Development: Pretty console output with colors
    if ENV == "development":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
            # ColoredConsoleRenderer()  # O usa el custom
        ]
    
    # Production: JSON output for log aggregation
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging (for libraries)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=LOG_LEVEL,
    )
    
    # Add JSON formatter to root logger in production
    if ENV != "development":
        root_logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CustomJsonFormatter())
        root_logger.handlers = [handler]
    
    print(f"✓ Logging configurado - Nivel: {LOG_LEVEL}, Entorno: {ENV}")

# ==========================================
# Logger factory
# ==========================================

def get_logger(name: str = None):
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        structlog.BoundLogger
    
    Example:
        logger = get_logger(__name__)
        logger.info("user_login", user_id="123", ip="192.168.1.1")
    """
    return structlog.get_logger(name)

# ==========================================
# Context managers for request tracking
# ==========================================

from contextvars import ContextVar
import uuid

# Context variables for tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
device_id_var: ContextVar[str] = ContextVar("device_id", default="")

def bind_request_context(request_id: str = None, user_id: str = None, device: str = None):
    """
    Bind context variables for the current request
    This makes them available in all logs within this context
    
    Example:
        bind_request_context(
            request_id="req-123",
            user_id="user-456",
            device="smartphone"
        )
    """
    if request_id:
        request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
    
    if user_id:
        user_id_var.set(user_id)
        structlog.contextvars.bind_contextvars(user_id=user_id)
    
    if device:
        device_id_var.set(device)
        structlog.contextvars.bind_contextvars(device=device)

def clear_request_context():
    """Clear all context variables"""
    structlog.contextvars.clear_contextvars()
    request_id_var.set("")
    user_id_var.set("")
    device_id_var.set("")

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return f"req-{uuid.uuid4().hex[:12]}"

# ==========================================
# Logging helpers for common patterns
# ==========================================

class LogEvent:
    """
    Standard log event names
    Helps maintain consistency across the codebase
    """
    
    # Authentication
    AUTH_TOKEN_VERIFIED = "auth.token_verified"
    AUTH_TOKEN_FAILED = "auth.token_failed"
    AUTH_KEY_VALIDATED = "auth.key_validated"
    AUTH_KEY_INVALID = "auth.key_invalid"
    
    # WebSocket
    WS_CONNECTION_ATTEMPT = "ws.connection_attempt"
    WS_CONNECTION_ESTABLISHED = "ws.connection_established"
    WS_CONNECTION_REJECTED = "ws.connection_rejected"
    WS_DISCONNECTED = "ws.disconnected"
    WS_FRAME_RECEIVED = "ws.frame_received"
    WS_FRAME_SENT = "ws.frame_sent"
    WS_FRAME_REJECTED = "ws.frame_rejected"
    WS_COMMAND_SENT = "ws.command_sent"
    WS_COMMAND_RECEIVED = "ws.command_received"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    RATE_LIMIT_CHECKED = "rate_limit.checked"
    
    # Storage
    FILE_UPLOADED = "storage.file_uploaded"
    FILE_DOWNLOADED = "storage.file_downloaded"
    FILE_DELETED = "storage.file_deleted"
    
    # Errors
    ERROR_VALIDATION = "error.validation"
    ERROR_DATABASE = "error.database"
    ERROR_NETWORK = "error.network"
    ERROR_INTERNAL = "error.internal"

# ==========================================
# Performance tracking decorator
# ==========================================

import time
from functools import wraps

def log_performance(event_name: str = None):
    """
    Decorator to automatically log function execution time
    
    Example:
        @log_performance("database.query")
        async def get_user(user_id: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            event = event_name or f"{func.__module__}.{func.__name__}"
            
            start_time = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000  # ms
                
                logger.debug(
                    event,
                    duration_ms=round(duration, 2),
                    status="success"
                )
                
                return result
            
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                
                logger.error(
                    event,
                    duration_ms=round(duration, 2),
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            event = event_name or f"{func.__module__}.{func.__name__}"
            
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000
                
                logger.debug(
                    event,
                    duration_ms=round(duration, 2),
                    status="success"
                )
                
                return result
            
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                
                logger.error(
                    event,
                    duration_ms=round(duration, 2),
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

# Initialize logging on import
configure_logging()