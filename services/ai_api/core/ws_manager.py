"""
WebSocket Connection Manager.

Manages active WebSocket connections, supports:
- Per-job connection tracking
- Broadcasting messages to connected clients
- Heartbeat/ping-pong keep-alive
- Graceful disconnect handling
- Max connections enforcement
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from services.ai_api.config import get_settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time streaming.

    Tracks connections by client_id and optionally by job_id
    for targeted message delivery during AI processing.
    """

    def __init__(self) -> None:
        # Active connections: client_id → WebSocket
        self._connections: dict[str, WebSocket] = {}
        # Job subscriptions: job_id → set of client_ids
        self._job_subscribers: dict[str, set[str]] = {}
        self._max_connections = get_settings().ws_max_connections

    @property
    def active_count(self) -> int:
        """Number of currently active connections."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """
        Accept a new WebSocket connection.

        Returns False if max connections reached.
        """
        if self.active_count >= self._max_connections:
            logger.warning(
                "Max connections (%d) reached. Rejecting %s",
                self._max_connections,
                client_id,
            )
            await websocket.close(code=1013, reason="Max connections reached")
            return False

        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info(
            "WebSocket connected: %s (total: %d)",
            client_id,
            self.active_count,
        )
        return True

    def disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""
        self._connections.pop(client_id, None)

        # Remove from all job subscriptions
        for subscribers in self._job_subscribers.values():
            subscribers.discard(client_id)

        logger.info(
            "WebSocket disconnected: %s (total: %d)",
            client_id,
            self.active_count,
        )

    def subscribe_to_job(self, client_id: str, job_id: str) -> None:
        """Subscribe a client to receive updates for a specific job."""
        if job_id not in self._job_subscribers:
            self._job_subscribers[job_id] = set()
        self._job_subscribers[job_id].add(client_id)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        """Send a JSON message to a specific client."""
        ws = self._connections.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning("Failed to send to %s: %s", client_id, e)
            self.disconnect(client_id)
            return False

    async def broadcast_to_job(self, job_id: str, message: dict[str, Any]) -> int:
        """
        Broadcast a message to all clients subscribed to a job.

        Returns the number of clients that received the message.
        """
        subscribers = self._job_subscribers.get(job_id, set())
        sent = 0
        for client_id in list(subscribers):
            if await self.send_to_client(client_id, message):
                sent += 1
        return sent

    async def send_bytes_to_client(self, client_id: str, data: bytes) -> bool:
        """Send binary data to a specific client."""
        ws = self._connections.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send_bytes(data)
            return True
        except Exception:
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Broadcast a message to all connected clients."""
        sent = 0
        for client_id in list(self._connections.keys()):
            if await self.send_to_client(client_id, message):
                sent += 1
        return sent


# Singleton instance
ws_manager = ConnectionManager()
