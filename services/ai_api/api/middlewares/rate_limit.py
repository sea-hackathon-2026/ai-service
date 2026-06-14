"""
Rate limiting middleware.

Simple in-memory rate limiter based on client IP.
For production, replace with Redis-backed rate limiting.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Default: 60 requests per minute per IP
DEFAULT_RATE_LIMIT = 60
DEFAULT_WINDOW_SEC = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token-bucket rate limiter per client IP."""

    def __init__(
        self,
        app,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_sec: int = DEFAULT_WINDOW_SEC,
    ) -> None:
        super().__init__(app)
        self._rate_limit = rate_limit
        self._window_sec = window_sec
        # IP → (request_count, window_start)
        self._buckets: dict[str, tuple[int, float]] = defaultdict(lambda: (0, time.time()))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        count, window_start = self._buckets[client_ip]
        now = time.time()

        # Reset window if expired
        if now - window_start > self._window_sec:
            count = 0
            window_start = now

        count += 1
        self._buckets[client_ip] = (count, window_start)

        if count > self._rate_limit:
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        f"Rate limit of {self._rate_limit} requests per "
                        f"{self._window_sec}s exceeded"
                    ),
                },
                headers={"Retry-After": str(int(self._window_sec - (now - window_start)))},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self._rate_limit - count))
        return response
