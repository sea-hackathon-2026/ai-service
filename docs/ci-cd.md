# CI/CD and Release Operations

## Delivery Model

The repository uses GitHub Actions as the control plane and GitHub Container
Registry (GHCR) as the artifact registry. A release is a tested, immutable set
of three service images built from the same Git commit.

```text
push or pull request
        |
        v
CI: dependency check -> lint -> compile -> tests
        |
        | successful push to main
        v
CD: build three Docker images -> publish latest + sha tags to GHCR
```

The CD workflow listens to the completed CI workflow rather than directly to a
push. This prevents a container from being published before the commit passes
the repository quality gates.

## Continuous Integration

`.github/workflows/ci.yml` runs on:

- every push to `main`;
- every pull request;
- manual dispatch from the GitHub Actions interface.

The job uses Python 3.11 and installs the AI API, RAG, and test dependency sets.
It intentionally does not install Google ADK because the default sales-agent
tests exercise deterministic domain tools without importing the provider
runtime. Provider-specific image installation is validated by the Docker build.

Quality gates execute in this order:

1. `pip check` rejects incompatible installed dependency graphs.
2. `ruff check services tests` enforces formatting-independent code quality and
   import rules.
3. `python -m compileall -q services tests` catches syntax and import-time source
   compilation errors.
4. `pytest -q` runs unit and integration tests without paid provider calls.

The workflow has read-only repository permissions. Concurrent runs for the same
branch are cancelled so reviewers see the result for the newest commit.

## Container Publishing

`.github/workflows/publish-images.yml` starts after a successful `CI` run on
`main`. A build matrix creates these images independently:

| Service | Dockerfile | GHCR image |
| --- | --- | --- |
| AI API | `services/ai_api/Dockerfile` | `ghcr.io/sea-hackathon-2026/ai-service-ai-api` |
| RAG service | `services/rag_service/Dockerfile` | `ghcr.io/sea-hackathon-2026/ai-service-rag-service` |
| Sales agent | `services/sales_agent/Dockerfile` | `ghcr.io/sea-hackathon-2026/ai-service-sales-agent` |

Each successful build publishes two tags:

- `latest` identifies the newest validated `main` release;
- `sha-<short-commit>` is immutable and should be used by production manifests.

The workflow uses the repository-scoped `GITHUB_TOKEN` with only `contents:read`
and `packages:write`. No personal access token is required. GitHub repository
settings must allow Actions to create and write packages.

## Deployment and Rollback

External environments should deploy immutable SHA tags. A deployment system can
watch GHCR, receive a registry webhook, or be triggered by a later environment-
specific workflow. Infrastructure credentials are intentionally not stored in
this repository because no single hosting platform is assumed.

Rollback consists of redeploying the previous known-good SHA tag. Rebuilding an
old commit is unnecessary and discouraged because it weakens artifact
traceability.

## Dependency Security

The previous `tests/frontend/package-lock.json` and the unused frontend were
removed from the monorepo. Therefore PostCSS is no longer in the source or image
dependency graph, which resolves the reported `< 8.5.10` advisory without
retaining an unowned frontend package.

`.github/dependabot.yml` monitors the remaining ecosystems:

- Python requirements under the repository root;
- versioned GitHub Actions used by CI/CD.

There is intentionally no npm Dependabot entry because the repository contains
no `package.json`, `package-lock.json`, or JavaScript deployable artifact.

## Verification Checklist

After merging or pushing to `main`:

1. Confirm the `CI` workflow succeeds for the expected commit SHA.
2. Confirm all three `Publish Containers` matrix jobs succeed.
3. Verify GHCR contains `latest` and the matching `sha-<commit>` tag.
4. Deploy the SHA tag and call each service `/health` endpoint.
5. Keep the previous SHA available until post-deployment checks complete.
