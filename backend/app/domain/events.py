from __future__ import annotations
import asyncio, time, uuid
from typing import Any, Callable, Dict, List
import logging
logger = logging.getLogger("shekar.events")

class DomainEvent:
    def __init__(self, event_type: str, payload: Dict[str, Any]):
        self.id = uuid.uuid4().hex[:12]
        self.type = event_type
        self.payload = payload
        self.timestamp = time.time()
    def to_dict(self):
        return {"id": self.id, "type": self.type, "payload": self.payload, "ts": self.timestamp}

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._history: List[DomainEvent] = []
        self._max_history = 500
    
    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: DomainEvent):
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        handlers = self._handlers.get(event.type, []) + self._handlers.get("*", [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.warning(f"Event handler failed: {exc}")
    
    def get_history(self, event_type: str = None, limit: int = 50):
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return [e.to_dict() for e in events[-limit:]]

event_bus = EventBus()
