# API Reference

## AI API (`:8000`)

All mutating generation endpoints require `X-API-Key`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Process liveness |
| GET | `/readiness` | Video and TTS adapter readiness |
| GET | `/v1/video/config` | Supported video parameters |
| POST | `/v1/video/generate` | Synchronous adapter-backed video generation |
| POST | `/v1/video/livestream/jobs` | Create an uploaded micro-scene render job |
| GET | `/v1/video/livestream/jobs/{id}/outputs` | Read scene and final outputs |
| GET | `/v1/tts/voices` | Available voices |
| POST | `/v1/tts/synthesize` | Synthesize speech |
| GET | `/v1/jobs/{id}` | Read job state |
| WS | `/v1/ws/video/generate` | Stream video chunks |
| WS | `/v1/ws/tts/stream` | Stream audio chunks |

Example:

```bash
curl -X POST http://localhost:8000/v1/tts/synthesize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-a-random-secret" \
  -d '{"text":"Xin chao","voice":"vi-female-01"}'
```

Generated media is served under `/outputs`. In production this should be
replaced by object storage rather than serving large files from the API process.

## RAG Service (`:8001`)

`POST /v1/retrieval/search` returns explainable knowledge chunks and requires no
model provider:

```json
{"query":"Gia livestream va uu dai?","top_k":3}
```

`POST /v1/scripts/generate` processes comments end to end:

```json
{
  "comments": [
    {"text": "Gia bao nhieu vay shop?", "timestamp": "2026-06-15T10:00:00Z"},
    {"text": "Co giao ve Ha Noi khong?"}
  ],
  "top_k": 3,
  "max_batch_size": 4
}
```

Generation returns `503` when `RAG_OPENAI_API_KEY` is not configured. Retrieval
remains available for diagnostics and offline evaluation.

## Sales Agent (`:8002`)

Start or continue a session:

```json
POST /v1/chat
{"message":"Minh muon mua hai san pham","session_id":null}
```

The response returns `reply`, `session_id`, and `fallback_used`. Send the same
session ID on the next turn. `POST /v1/sessions/reset` creates a fresh session.

The current session store is process-local. A load-balanced deployment requires
sticky routing or a durable ADK session adapter.
