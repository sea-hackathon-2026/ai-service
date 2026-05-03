"""
Auth middleware for request-level API key validation.

Note: For endpoint-level auth, use the `ApiKeyDep` dependency from deps.py.
This middleware is for global auth enforcement on all routes.
"""

from __future__ import annotations

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.security import verify_api_key

logger = logging.getLogger(__name__)

# Routes that don't require authentication
PUBLIC_PATHS = {"/health", "/readiness", "/docs", "/redoc", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional global API key authentication middleware."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth for public paths and WebSocket upgrades
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/ws"):
            return await call_next(request)

        # Skip OPTIONS (preflight) requests
        if request.method == "OPTIONS":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key or not verify_api_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "message": "Invalid or missing API key"},
            )

        return await call_next(request)
