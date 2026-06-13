# ADR-011 — RAG retrieval quality: embedding task prefixes + opt-in hybrid reranking

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive — a correctness fix to the default embedding
  path plus opt-in retrieval knobs; the dense-vector retrieval contract is
  unchanged and every new knob defaults to current behaviour or OFF)

---

## Context

Retrieval across the stack was **dense-vector-only**. Open WebUI, the async
ingestion worker, and the Pydantic AI knowledge-base tool all embed text with
Ollama (`nomic-embed-text`, the chart default) and query Qdrant by cosine
similarity. Two quality gaps had accumulated:

1. **Missing embedding task prefixes.** `nomic-embed-text` is instruction-tuned
   and **requires** a task prefix: `search_query: ` on queries and
   `search_document: ` on stored passages (per the model card). The stack
   embedded raw text on every surface, with no prefix — a silent
   retrieval-quality regression for the default embedder, and an inconsistency
   risk if any single surface were fixed in isolation.
2. **No lexical leg, no reranking.** Dense-only retrieval misses exact-term
   matches (error codes, identifiers, function names) and has no second-stage
   precision pass. The established higher-quality pipeline is **hybrid**
   retrieval (a BM25 lexical leg fused with dense results, classically by
   Reciprocal Rank Fusion) followed by a **cross-encoder reranking** stage.

Constraints that shaped the decision:

- **Secure by default.** PSA `restricted`, default-deny NetworkPolicy, and
  air-gap/Zarf parity. A reranking model is downloaded from Hugging Face **at
  runtime** — that needs egress the default posture does not grant.
- **Never weaken a default**, and `values.yaml` is the source of truth.
- **Surgical change.** The per-component `.Values.<component>.env` passthrough
  already renders arbitrary env into the container; `values.schema.json` is
  `additionalProperties: true`, so new knobs need no template logic or schema
  change.

## Decision

1. **Apply `nomic-embed-text` task prefixes by default on every embedding
   surface.** Two knobs — `RAG_EMBEDDING_QUERY_PREFIX` (`"search_query: "`) and
   `RAG_EMBEDDING_CONTENT_PREFIX` (`"search_document: "`) — are set in
   `openwebui.env` (Open WebUI consumes these natively), and the in-repo
   ingestion worker (content prefix) and Pydantic AI app (query prefix) read the
   same env names. The apps default the prefix to empty in code (model-agnostic
   when run outside the chart) and prepend it to the **embedding input only**,
   leaving the stored Qdrant payload text unchanged. Query and document prefixes
   are paired per collection, so each writer/reader pair stays in the same
   embedding space.

2. **Hybrid retrieval and cross-encoder reranking are opt-in, OFF by default.**
   New `openwebui.env` knobs: `ENABLE_RAG_HYBRID_SEARCH` (`false`),
   `RAG_RERANKING_MODEL` (`""`), `RAG_RERANKING_ENGINE` (`""`),
   `RAG_TOP_K_RERANKER` (`20`, the validated retrieve-wide-then-rerank range vs.
   Open WebUI's own default of 3), and `RAG_HYBRID_BM25_WEIGHT` (`0.5`). They are
   OFF by default because enabling reranking pulls a model from Hugging Face at
   runtime; that requires an egress grant or a pre-staged model, which is a
   conscious operator decision, not a shipped default.

3. **Reranker model license guidance.** Recommend small, Apache-2.0
   cross-encoders (`BAAI/bge-reranker-v2-m3`,
   `cross-encoder/ms-marco-MiniLM-L-6-v2`). No reranker model is shipped or set
   by default. The model is a **runtime artifact** (like the embedding model and
   the LLMs), not a container image, so it is not part of the image SBOM / Zarf
   set; its license is tracked in
   [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md).

4. **Align the ingestion worker's `RAG_CHUNK_OVERLAP` code default** (was `100`)
   with the chart value and Open WebUI (`150`) so a chartless run matches the
   deployed splitter.

**Deferred (documented follow-ups, not in this change):**

- Qdrant collection-creation tuning (HNSW `m`/`ef_construct`/`ef_search`, scalar
  int8 quantization). The worker upserts points but does not create the
  collection, so index parameters need collection-ownership clarity first.
- Per-tenant / per-agent Qdrant collection isolation (the worker upserts all
  tasks to one configured collection — a known gap in `ingestion-worker-spec.md`).
- Structured agent memory (episodic/semantic separation, recency/salience
  scoring, compaction, bitemporal facts) — a larger architectural change.

## Consequences

**Positive**

- Correct embedding behaviour for the shipped default model, consistently across
  all three retrieval surfaces.
- A documented, low-effort path to hybrid + reranking (a large retrieval-quality
  gain in the literature) without changing the secure default.
- The security default is unchanged: no egress, no runtime model download until
  an operator opts in. Asserted in `tests/rag_retrieval_test.yaml`.

**Negative / trade-offs**

- **Re-index required on upgrade.** Changing the prefixes changes the embedding
  space, so collections / Open WebUI knowledge embedded **before** this change
  must be re-indexed to benefit and to avoid mixed-prefix drift. Greenfield
  deployments are correct immediately; the upgrade step is documented in
  `CHANGELOG.md` and the component docs.
- Enabling hybrid couples to a reranker model in Open WebUI: BM25 itself is
  local, but the supported path sets `RAG_RERANKING_MODEL`, so enabling needs an
  egress grant or a pre-staged model.

## Alternatives considered

- **Default-on hybrid + reranking.** Strictly higher quality, but the runtime
  model download breaks the default-deny / air-gap posture — it would weaken a
  shipped default. Rejected in favour of opt-in plus documentation.
- **A structured `openwebui.rag.*` values block with template conditionals.**
  Rejected — the `.env` passthrough already covers it; a structured block adds
  template logic and a schema surface for no functional gain.
- **Leaving the prefixes opt-in.** Rejected — the chart's default embedder
  *requires* them; opt-in would ship a known-suboptimal default.
- **Pinning a default reranker model.** Rejected — it would imply a default
  runtime download (egress) and bake a model choice into the chart; the operator
  picks the model when they opt in.

## Validation and sources

- `nomic-embed-text` task prefixes and Matryoshka dimensions: the model card
  (`huggingface.co/nomic-ai/nomic-embed-text-v1.5`).
- Reciprocal Rank Fusion and the `k = 60` constant: Cormack, Clarke & Büttcher,
  SIGIR 2009. Hybrid = BM25 + HNSW fused by RRF, then a semantic reranker:
  Microsoft Azure AI Search documentation. The contextual-retrieval quality
  ladder (contextual embeddings reduced failed retrievals 35%, adding lexical
  BM25 49%, adding reranking 67%): Anthropic, *Introducing Contextual Retrieval*.
- Open WebUI env semantics (`ENABLE_RAG_HYBRID_SEARCH`, `RAG_RERANKING_MODEL`,
  `RAG_RERANKING_ENGINE`, `RAG_TOP_K_RERANKER`, `RAG_HYBRID_BM25_WEIGHT`,
  `RAG_EMBEDDING_QUERY_PREFIX`, `RAG_EMBEDDING_CONTENT_PREFIX`): the Open WebUI
  backend configuration.
- Reranker model licenses: `BAAI/bge-reranker-v2-m3` (Apache-2.0),
  `cross-encoder/ms-marco-MiniLM-L-6-v2` (Apache-2.0).
