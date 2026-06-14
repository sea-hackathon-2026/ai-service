"""
Video Generation WebSocket endpoint.

Flow:
1. Client connects to /ws/video/generate
2. Client sends auth message: {"type": "authenticate", "api_key": "..."}
3. Server responds: {"type": "authenticated", "session_id": "..."}
4. Client sends: {"type": "generate", "prompt": "...", "config": {...}}
5. Server streams back:
   - {"type": "progress", "percent": 25, "stage": "encoding_frames", ...}
   - {"type": "frame_chunk", "data": "<base64>", "frame_idx": 0, ...}
   - {"type": "complete", "video_url": "...", "job_id": "..."}
6. On error: {"type": "error", "code": "...", "message": "..."}
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.ai_api.api.deps import video_stream_use_case
from services.ai_api.application.dto.video_request import VideoRequest
from services.ai_api.core.security import verify_api_key
from services.ai_api.core.ws_manager import ws_manager
from services.ai_api.domain.exceptions.base import DomainException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/video/generate")
async def video_generate_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time video generation with chunk streaming.

    The client must authenticate first, then send a generate request.
    The server will stream progress updates and frame chunks back in real-time.
    """
    client_id = str(uuid.uuid4())

    # Accept connection
    if not await ws_manager.connect(websocket, client_id):
        return  # Max connections reached

    authenticated = False

    try:
        while True:
            # Receive message from client
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

            # ── Handle ping ──
            if msg_type == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": time.time(),
                    }
                )
                continue

            # ── Handle authentication ──
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

            # ── Require auth for all other messages ──
            if not authenticated:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "NOT_AUTHENTICATED",
                        "message": (
                            "Authenticate first with a message containing "
                            "type=authenticate and api_key."
                        ),
                    }
                )
                continue

            # ── Handle generate ──
            if msg_type == "generate":
                prompt = message.get("prompt", "")
                config = message.get("config", {})

                if not prompt:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "INVALID_PROMPT",
                            "message": "Prompt is required",
                        }
                    )
                    continue

                # Build request DTO
                dto = VideoRequest(
                    prompt=prompt,
                    width=config.get("width", 512),
                    height=config.get("height", 512),
                    num_frames=config.get("num_frames", 16),
                    fps=config.get("fps", 24),
                    duration_sec=config.get("duration_sec", 2.0),
                    guidance_scale=config.get("guidance_scale", 6.0),
                    num_inference_steps=config.get("num_inference_steps", 50),
                    seed=config.get("seed"),
                )

                async with video_stream_use_case() as use_case:
                    try:
                        job_id = None
                        total_chunks = 0

                        async for chunk in use_case.execute_stream(dto):
                            job_id = chunk.job_id

                            # Send progress update
                            progress_pct = 0.0
                            if chunk.total_frames:
                                progress_pct = (chunk.frame_idx + 1) / chunk.total_frames * 100

                            await websocket.send_json(
                                {
                                    "type": "progress",
                                    "job_id": chunk.job_id,
                                    "percent": round(progress_pct, 1),
                                    "stage": f"generating_frame_{chunk.frame_idx}",
                                }
                            )

                            # Send frame chunk (base64 encoded)
                            await websocket.send_json(
                                {
                                    "type": "frame_chunk",
                                    "job_id": chunk.job_id,
                                    "data": base64.b64encode(chunk.data).decode(),
                                    "chunk_idx": chunk.chunk_idx,
                                    "frame_idx": chunk.frame_idx,
                                    "total_frames": chunk.total_frames,
                                }
                            )

                            total_chunks += 1

                            # Send completion on final chunk
                            if chunk.is_final:
                                await websocket.send_json(
                                    {
                                        "type": "complete",
                                        "job_id": chunk.job_id,
                                        "total_chunks": total_chunks,
                                        "url": f"/outputs/videos/{chunk.job_id}.mp4",
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
                        logger.error("Video WS error: %s", e, exc_info=True)
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "INTERNAL_ERROR",
                                "message": str(e),
                            }
                        )

                continue

            # ── Unknown message type ──
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "UNKNOWN_TYPE",
                    "message": f"Unknown message type: '{msg_type}'",
                }
            )

    except WebSocketDisconnect:
        logger.info("Video WS client disconnected: %s", client_id)
    except Exception as e:
        logger.error("Video WS unexpected error: %s", e, exc_info=True)
    finally:
        ws_manager.disconnect(client_id)
