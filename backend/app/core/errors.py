"""
errors.py - v0.6.2 - P2-3 Fix: Structured errors with error_id
"""
import uuid
import logging
from typing import Any, Dict

logger = logging.getLogger("shekar.errors")

def create_error_id() -> str:
    return uuid.uuid4().hex[:8]

def log_error_with_id(msg: str, exc: Exception = None, context: Dict[str, Any] = None) -> str:
    err_id = create_error_id()
    full_msg = f"[{err_id}] {msg}"
    if context:
        full_msg += f" | context={context}"
    if exc:
        logger.exception(full_msg, exc_info=exc)
    else:
        logger.error(full_msg)
    return err_id

class AppError(Exception):
    def __init__(self, message: str, code: str = "INTERNAL", status_code: int = 500, context: Dict[str, Any] = None):
        self.error_id = create_error_id()
        self.message = message
        self.code = code
        self.status_code = status_code
        self.context = context or {}
        super().__init__(f"[{self.error_id}] {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "code": self.code,
            "message": self.message,
            "context": self.context
        }
