# RAG Service

This service converts noisy livestream comments into grounded presenter scripts.
It owns deterministic filtering, intent classification, batching, lexical TF-IDF
retrieval, and provider-backed response generation.

## Run

```bash
uvicorn services.rag_service.main:app --reload --port 8001
```

`POST /v1/retrieval/search` works without external credentials. Script generation
requires `RAG_OPENAI_API_KEY`; the model defaults to `gpt-4o-mini` and can be
changed with `RAG_OPENAI_MODEL`.

The application layer depends only on the `KnowledgeRepository` and
`ScriptGenerator` protocols. This keeps retrieval storage and LLM providers
replaceable without changing domain policies or HTTP schemas.
