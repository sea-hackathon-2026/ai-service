# Development Guide

## Local Environment

Use Python 3.11. Install all services and development tools with
`pip install -r requirements.txt`. Copy `.env.example` to `.env`; never commit
the populated file.

Each service can be installed independently in CI or Docker through its file in
`requirements/`. This prevents the lightweight RAG container from inheriting
media dependencies and prevents the AI API from requiring Google ADK.

## Running and Testing

```bash
ruff check services tests
pytest -q
docker compose config
```

Integration tests override `get_async_session`, so the API repository receives
the same in-memory engine whose tables are created by the fixture. This is the
required pattern for new persistence tests; changing a module-level engine does
not replace an already-wired FastAPI dependency.

## CI/CD Expectations

Every pull request must pass the same Ruff, compilation, dependency, and pytest
commands used locally. A successful CI run on `main` triggers the container
publishing workflow; failed or cancelled CI runs publish nothing. Service images
are tagged with both `latest` and the source commit SHA so environments can pin
an immutable release and roll back without rebuilding code.

See [CI/CD and Release Operations](ci-cd.md) for workflow permissions, image
names, release verification, and rollback behavior.

## Adding a Model Adapter

1. Identify the domain port, such as `IVideoService`, `ITTSService`, or
   `ScriptGenerator`.
2. Implement the port under the owning service's `infrastructure/` package.
3. Translate SDK responses into domain models inside the adapter.
4. Select the adapter in `api/deps.py` or `api/dependencies.py`.
5. Add contract tests using a fake SDK client. Do not call paid providers in the
   default test suite.

Provider exceptions must not escape directly through HTTP. Map them to domain
or application errors, then translate those errors in the FastAPI composition
root.

## Adding an Endpoint

Transport schemas belong in `api/schemas.py`. Endpoints should perform only
validation, DTO mapping, dependency resolution, and response mapping. Business
branching belongs in a use case or domain policy. Database sessions and SDK
clients must be injected rather than instantiated in route functions.

## Updating Product Knowledge

The sample corpus is `services/rag_service/resources/knowledge_base.json`.
Override `RAG_KNOWLEDGE_BASE_PATH` for another tenant or catalog. Treat the
knowledge snapshot as versioned model input: validate its schema, record its
version with generated outputs, and run retrieval evaluation before release.

## Code Comments

Prefer module and public-symbol docstrings that explain ownership, invariants,
or architectural intent. Inline comments are reserved for non-obvious provider
behavior, transaction boundaries, and media-processing constraints. Avoid
comments that merely repeat the next line of code.

## Pull Request Checklist

- Dependency direction remains API/infrastructure toward application/domain.
- New model or database code is behind a port.
- Error and timeout behavior is explicit.
- Unit tests cover policies; integration tests cover wiring.
- No secret, generated media, copied project, or experimental notebook is added.
- Documentation and `.env.example` reflect new public configuration.
