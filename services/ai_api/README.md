# AI API

Job-oriented media orchestration service for video, speech, and livestream
micro-scene rendering. Domain ports isolate model, storage, and persistence
implementations from application use cases.

```bash
uvicorn services.ai_api.main:app --reload --port 8000
```

The default video and TTS adapters are deterministic mocks suitable for API
integration and architecture review. Configure the Google GenAI and local media
pipeline settings to exercise external generation paths.
