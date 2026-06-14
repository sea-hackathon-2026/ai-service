"""
TTS Streaming WebSocket endpoint.

Flow:
1. Client connects to /ws/tts/stream
2. Client sends auth: {"type": "authenticate", "api_key": "..."}
3. Server responds: {"type": "authenticated", "session_id": "..."}
4. Client sends: {"type": "synthesize", "text": "...", "voice": "vi-female-01", "format": "wav"}
5. Server streams audio chunks:
   - {"type": "audio_chunk", "data": "<base64_pcm>", "chunk_idx": 0, "sample_rate": 22050, ...}
   - {"type": "audio_chunk", "data": "<base64_pcm>", "chunk_idx": 1, ...}
   - {"type": "complete", "total_chunks": 15, "duration_ms": 3200, ...}
6. Client can play each chunk immediately for real-time audio playback
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.ai_api.api.deps import tts_stream_use_case
from services.ai_api.application.dto.tts_request import TTSRequest
from services.ai_api.core.security import verify_api_key
from services.ai_api.core.ws_manager import ws_manager
from services.ai_api.domain.exceptions.base import DomainException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/tts/stream")
async def tts_stream_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time TTS audio chunk streaming.

    The client receives audio chunks as they are synthesized,
    enabling immediate playback before the full audio is ready.
    """
    client_id = str(uuid.uuid4())

    if not await ws_manager.connect(websocket, client_id):
        return

    authenticated = False

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "INVALID_JSON",
                        "message": "Message must be valid JSON",
                    }
                )
                continue

            msg_type = message.get("type", "")

            # ── Ping/Pong ──
            if msg_type == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": time.time(),
                    }
                )
                continue

            # ── Authentication ──
            if msg_type == "authenticate":
                api_key = message.get("api_key", "")
                if verify_api_key(api_key):
                    authenticated = True
                    await websocket.send_json(
                        {
                            "type": "authenticated",
                            "session_id": client_id,
                        }
                    )
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "AUTH_FAILED",
                            "message": "Invalid API key",
                        }
                    )
                continue

            # ── Require auth ──
            if not authenticated:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "NOT_AUTHENTICATED",
                        "message": "Please authenticate first",
                    }
                )
                continue

            # ── Synthesize ──
            if msg_type == "synthesize":
                text = message.get("text", "")
                voice = message.get("voice", "default")
                language = message.get("language", "vi")
                audio_format = message.get("format", "wav")

                if not text:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "EMPTY_TEXT",
                            "message": "Text is required",
                        }
                    )
                    continue

                dto = TTSRequest(
                    text=text,
                    voice=voice,
                    language=language,
                    audio_format=audio_format,
                )

                async with tts_stream_use_case() as use_case:
                    try:
                        job_id = None
                        total_chunks = 0
                        total_duration_ms = 0.0

                        async for chunk in use_case.execute_stream(dto):
                            job_id = chunk.job_id
                            total_chunks += 1
                            total_duration_ms += chunk.duration_ms

                            # Stream audio chunk (base64 encoded for JSON transport)
                            await websocket.send_json(
                                {
                                    "type": "audio_chunk",
                                    "job_id": chunk.job_id,
                                    "data": base64.b64encode(chunk.data).decode(),
                                    "chunk_idx": chunk.chunk_idx,
                                    "sample_rate": chunk.sample_rate,
                                    "channels": chunk.channels,
                                    "format": chunk.format,
                                    "duration_ms": round(chunk.duration_ms, 2),
                                    "is_final": chunk.is_final,
                                }
                            )

                            # Send completion message on final chunk
                            if chunk.is_final:
                                await websocket.send_json(
                                    {
                                        "type": "complete",
                                        "job_id": chunk.job_id,
                                        "total_chunks": total_chunks,
                                        "duration_ms": round(total_duration_ms, 2),
                                    }
                                )

                    except DomainException as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": e.code,
                                "message": e.message,
                                "job_id": job_id,
                            }
                        )
                    except Exception as e:
                        logger.error("TTS WS error: %s", e, exc_info=True)
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "INTERNAL_ERROR",
                                "message": str(e),
                            }
                        )

                continue

            # ── Unknown ──
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "UNKNOWN_TYPE",
                    "message": f"Unknown message type: '{msg_type}'",
                }
            )

    except WebSocketDisconnect:
        logger.info("TTS WS client disconnected: %s", client_id)
    except Exception as e:
        logger.error("TTS WS unexpected error: %s", e, exc_info=True)
    finally:
        ws_manager.disconnect(client_id)
