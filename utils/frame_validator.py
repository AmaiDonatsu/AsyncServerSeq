"""
Frame validation utilities
Ensures frames are within acceptable size limits
"""

from typing import Tuple
from datetime import datetime, timedelta

# Frame size limits (bytes)
MIN_FRAME_SIZE = 1024           # 1 KB - minimum viable frame
MAX_FRAME_SIZE = 5 * 1024 * 1024  # 5 MB - maximum to prevent memory issues
OPTIMAL_FRAME_SIZE = 500 * 1024   # 500 KB - recommended size

# FPS throttling
MAX_FPS = 30
MIN_FRAME_INTERVAL = 1.0 / MAX_FPS  # Minimum time between frames (seconds)

class FrameValidator:
    """
    Validates incoming frames for size and rate
    """
    
    def __init__(self):
        self.last_frame_time = {}
        
        self.frame_stats = {}  # connection_id -> {count, total_bytes, start_time}
    
    def validate_frame_size(self, frame_data: bytes) -> Tuple[bool, str, str]:
        """
        Validate frame size
        
        Returns:
            (is_valid: bool, status: str, message: str)
        """
        size = len(frame_data)
        
        if size < MIN_FRAME_SIZE:
            return False, "too_small", f"Frame too small: {size} bytes (min: {MIN_FRAME_SIZE})"
        
        if size > MAX_FRAME_SIZE:
            return False, "too_large", f"Frame too large: {size} bytes (max: {MAX_FRAME_SIZE})"
        
        if size > OPTIMAL_FRAME_SIZE:
            return True, "warning", f"Frame larger than optimal: {size} bytes (recommended: {OPTIMAL_FRAME_SIZE})"
        
        return True, "ok", "Frame size OK"
    
    def validate_frame_rate(self, connection_id: str) -> Tuple[bool, str]:
        """
        Validate that frames aren't being sent too quickly
        
        Returns:
            (is_valid: bool, message: str)
        """
        now = datetime.now()
        
        if connection_id not in self.last_frame_time:
            self.last_frame_time[connection_id] = now
            return True, "OK"
        
        last_time = self.last_frame_time[connection_id]
        time_since_last = (now - last_time).total_seconds()
        
        if time_since_last < MIN_FRAME_INTERVAL:
            current_fps = 1.0 / time_since_last if time_since_last > 0 else 999
            return False, f"Frame rate too high: {current_fps:.1f} FPS (max: {MAX_FPS})"
        
        self.last_frame_time[connection_id] = now
        return True, "OK"
    
    def record_frame(self, connection_id: str, frame_size: int):
        """Record frame statistics for monitoring"""
        now = datetime.now()
        
        if connection_id not in self.frame_stats:
            self.frame_stats[connection_id] = {
                "count": 0,
                "total_bytes": 0,
                "start_time": now
            }
        
        stats = self.frame_stats[connection_id]
        stats["count"] += 1
        stats["total_bytes"] += frame_size
    
    def get_stats(self, connection_id: str) -> dict:
        """Get statistics for a connection"""
        if connection_id not in self.frame_stats:
            return {}
        
        stats = self.frame_stats[connection_id]
        elapsed = (datetime.now() - stats["start_time"]).total_seconds()
        
        if elapsed == 0:
            return stats
        
        avg_fps = stats["count"] / elapsed
        avg_frame_size = stats["total_bytes"] / stats["count"] if stats["count"] > 0 else 0
        bandwidth_mbps = (stats["total_bytes"] * 8) / (elapsed * 1_000_000)  # Megabits per second
        
        return {
            "total_frames": stats["count"],
            "total_bytes": stats["total_bytes"],
            "duration_seconds": elapsed,
            "avg_fps": round(avg_fps, 2),
            "avg_frame_size_kb": round(avg_frame_size / 1024, 2),
            "bandwidth_mbps": round(bandwidth_mbps, 2)
        }
    
    def cleanup_connection(self, connection_id: str):
        """Clean up tracking data for a disconnected connection"""
        self.last_frame_time.pop(connection_id, None)
        self.frame_stats.pop(connection_id, None)

frame_validator = FrameValidator()