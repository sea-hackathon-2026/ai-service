# System Architecture

## Architectural Goals

The platform is organized as a monorepo because the services belong to one
product and share engineering standards, but they have different scaling and
dependency profiles. Video workloads need GPU and FFmpeg resources, retrieval
is CPU-bound and low latency, and the conversational agent owns stateful model
sessions. Independent processes prevent one workload from forcing every other
workload to carry the same runtime cost.

The design optimizes for:

1. **Explicit ownership**: every service owns its API, configuration, runtime,
   and provider adapters.
2. **Dependency inversion**: application use cases depend on protocols or
   abstract interfaces, not SDKs and databases.
3. **Testability**: model providers and persistence are replaceable at the
   composition root.
4. **Operational clarity**: each service has one entrypoint, health endpoint,
   Dockerfile, and dependency set.

## Service Boundaries

### AI API

The AI API is an orchestration service, not a model implementation. Its domain
contains jobs, media results, scene plans, status transitions, and ports for
video, TTS, storage, and persistence. Application use cases coordinate these
ports. Infrastructure currently includes mock video/TTS adapters, local media
storage, SQLAlchemy persistence, Google GenAI integration, and the local
micro-scene pipeline.

Long-running livestream rendering uses a `JobUnitOfWork` port. Background
progress updates therefore open independent transactions without importing
SQLAlchemy into the application layer. This also prevents request-scoped
sessions from leaking into background tasks.

### RAG Service

The RAG service owns the complete grounding path:

```text
comments -> noise filtering -> intent classification -> batching
         -> retrieval -> prompt construction -> structured generation
```

Classification and batching are deterministic domain policies. Retrieval and
generation are ports. The included JSON adapter builds an in-memory TF-IDF
index, which is appropriate for a small product catalog and gives explainable
retrieved tags. A vector database can replace it without changing the use case
or HTTP schema.

### Sales Agent

The sales agent owns conversational session state and order-closing behavior.
FastAPI does not directly call Google ADK primitives. `SalesAgentRuntime`
encapsulates ADK sessions, runner execution, final-response extraction, and
quota fallback. Pure order validation remains independently testable.

The current session adapter is in-memory. A production deployment should use a
durable session implementation before horizontal scaling.

## Dependency Rules

- `domain/` imports only Python standard-library types and other domain code.
- `application/` may import domain models and ports, but not FastAPI or provider
  SDKs.
- `infrastructure/` implements domain/application ports using concrete SDKs.
- `api/` validates transport data and maps it to use-case inputs.
- `main.py` is the composition root where concrete adapters are selected.

The media pipeline is currently retained under infrastructure because it
contains FFmpeg, filesystem, TTS, Wav2Lip, and model-provider concerns. Its
scene entities remain in the domain because they express provider-independent
planning concepts.

## Persistence and Transactions

Standard video/TTS requests use a request-scoped SQLAlchemy repository. The
FastAPI session dependency commits on success and rolls back on failure.
Livestream background work uses a unit of work per state transition because a
request session must not survive after the HTTP response.

SQLite is the local default. PostgreSQL can replace it through
`AI_API_DATABASE_URL`; repository behavior remains unchanged.

## Deployment Model

Docker Compose runs three independent containers on ports 8000-8002. Generated
media is mounted only into the AI API container. Model keys are supplied through
environment variables and are never embedded in images or notebooks.

The Colab notebook is a development GPU host for the AI API. It is not the
production control plane: ngrok URLs are ephemeral, Colab storage is temporary,
and a single notebook process provides no autoscaling or durability.

## Known Production Extensions

- Replace mock model adapters with managed endpoints or loaded GPU workers.
- Move job execution to a durable queue when multiple workers are introduced.
- Store media in object storage and return signed URLs.
- Replace in-memory agent sessions with Redis or a database-backed ADK session
  service.
- Add OpenTelemetry traces that propagate job, batch, and session identifiers.
- Add database migrations instead of startup-time `create_all`.
