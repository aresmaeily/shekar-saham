"""
audit.py - v0.7.0 Excellent - Audit logging - Security P0
"""
from __future__ import annotations

import time
import logging
from typing import Any, Dict
from fastapi import Request

logger = logging.getLogger("shekar.audit")

class AuditLogger:
    def __init__(self):
        self.enabled = True
    
    def log(self, action: str, user: str = "anonymous", resource: str = "", details: Dict[str, Any] = None, request: Request = None):
        if not self.enabled:
            return
        entry = {
            "ts": time.time(),
            "action": action,
            "user": user,
            "resource": resource,
            "details": details or {},
            "ip": request.client.host if request and request.client else "unknown",
            "path": request.url.path if request else resource,
        }
        # In production, send to SIEM or secure log
        logger.info(f"AUDIT: {entry}")
        # Also save to store for UI
        try:
            from app.data.store import store
            store.save_notify_log({"channel": "audit", "ok": True, "payload_json": str(entry), "text": f"AUDIT {action} by {user}"})
        except Exception:
            pass

audit = AuditLogger()
