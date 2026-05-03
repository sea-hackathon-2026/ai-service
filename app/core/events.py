"""
Internal event bus for decoupled communication between layers.

Allows use cases to emit events (e.g., progress updates) that
the API layer can subscribe to for WebSocket forwarding.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List

logger = logging.getLogger(__name__)

# Type alias for async event handlers
EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-process async event bus."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(
                    "Event handler error for '%s': %s", event_type, e
                )


# Event type constants
class Events:
    """Event type identifiers."""

    VIDEO_PROGRESS = "video.progress"
    VIDEO_CHUNK = "video.chunk"
    VIDEO_COMPLETE = "video.complete"
    VIDEO_ERROR = "video.error"
    TTS_PROGRESS = "tts.progress"
    TTS_CHUNK = "tts.chunk"
    TTS_COMPLETE = "tts.complete"
    TTS_ERROR = "tts.error"


# Singleton instance
event_bus = EventBus()
