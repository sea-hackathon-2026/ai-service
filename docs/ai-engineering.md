# AI and Agent Engineering

## RAG Design

The product knowledge corpus is small and structured, so the default retriever
uses normalized TF-IDF cosine similarity rather than a vector database. This is
a deliberate baseline: it is deterministic, inexpensive, explainable, and easy
to evaluate. Each top-level JSON knowledge section becomes a tagged chunk.
Responses expose retrieved tags so grounding failures can be inspected.

The retrieval adapter can later be replaced by embeddings and a vector store
behind `KnowledgeRepository`. A migration is justified when lexical retrieval
misses semantic paraphrases, the catalog becomes large, or metadata filtering
and multilingual retrieval become material requirements.

## Comment Processing

Rule-based preprocessing removes empty and engagement-only messages before any
LLM call. Regex intent classification then assigns a confidence priority.
Comments with the same intent are batched to reduce token cost and prevent the
presenter from answering equivalent questions repeatedly.

This hybrid design reserves model inference for natural-language generation,
while cheap and observable policies handle routing. New intent rules belong in
the domain classifier and require unit tests for positive and conflicting
phrases.

## Grounded Generation

The OpenAI adapter receives only normalized comments, dominant intent, and
retrieved context. It requests a JSON object containing response text, emotion,
call to action, and confidence. The system prompt explicitly requires the model
to acknowledge missing context rather than invent product facts.

Recommended production guardrails:

- Validate output with a strict provider-independent schema.
- Reject medical, pricing, or logistics claims that lack a retrieved source.
- Record prompt version, model version, retrieved chunk IDs, token usage, and
  latency for every generation.
- Apply PII redaction before comments enter logs or evaluation datasets.
- Use a circuit breaker and bounded retries for transient provider failures.

## Agent Design

The sales agent uses tools for deterministic order operations and an LLM for
conversation policy. The model must collect exactly five required fields and
call `confirm_order` only when complete. Tool validation prevents unknown or
empty fields from entering downstream systems.

Quota fallback is implemented at the runtime adapter. Only quota exhaustion
triggers the fallback model; arbitrary primary failures are surfaced rather
than hidden. The API response exposes `fallback_used` for monitoring and cost
analysis.

In a production commerce system, `confirm_order` should publish a command to an
order service rather than returning an in-memory dictionary. Idempotency keys,
phone validation, consent, and payment boundaries must be handled outside the
LLM.

## Media Generation

The AI API models generation as jobs with explicit status and progress. The
micro-scene pipeline decomposes a long livestream script into short scenes,
generates speech and visuals, optionally applies lip sync, and concatenates the
final output. Model adapters remain replaceable through video and TTS ports.

The local pipeline is useful as a fallback and demonstrator. Production GPU
execution should isolate model memory from the API process and use durable job
delivery. Job state must remain the source of truth even when a worker crashes.

## Evaluation Strategy

An AI engineering evaluation suite should contain:

| Component | Offline metric | Online signal |
|---|---|---|
| Intent classifier | macro F1, confusion matrix | correction rate |
| Retrieval | Recall@K, MRR, tag coverage | unsupported-answer rate |
| Script generation | groundedness, answer relevance, tone rubric | engagement and escalation |
| Sales agent | field completion, duplicate-question rate | conversion and abandonment |
| Media pipeline | render success, A/V sync error, latency | completion and replay rate |

Golden examples should be versioned with the prompt and knowledge snapshot.
LLM-as-judge scores should be calibrated against human labels and never be the
only release gate.

## Observability

Use correlation identifiers at three levels:

- `job_id` for media generation and background progress.
- `batch_id` or request ID for RAG retrieval and generation.
- `session_id` for multi-turn agent interactions.

Track latency by stage, provider error class, fallback rate, retrieval scores,
token usage, generated-media size, and queue time. Do not log raw phone numbers,
addresses, API keys, uploaded media, or full customer conversations by default.
