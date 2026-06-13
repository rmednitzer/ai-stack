# Open WebUI

Primary user-facing chat UI and orchestrator for the ai-stack. Handles authentication, conversation state, model selection (local and external), RAG document upload, and routing to Ollama, Qdrant, Tika, SearXNG, MCPO, LangGraph, and Pydantic AI. Runs as a stateless, horizontally-scalable service — session and config state live in the shared PostgreSQL and Valkey (see [High availability](#high-availability)).

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: enabled
- **Upstream**: <https://github.com/open-webui/open-webui> · [docs](https://docs.openwebui.com/)
- **Default image**: `ghcr.io/open-webui/open-webui` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/openwebui/`](../../templates/openwebui/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `openwebui.enabled` | Toggle the component |
| `openwebui.image.{repository,tag}` | Container image override |
| `openwebui.replicaCount` | Replicas (prod overlay sets HA) |
| `openwebui.secretKey` | Signs sessions/JWTs; auto-generated, stable across restarts and replicas |
| `openwebui.oauthTokenEncryptionKey` | Encrypts OAuth session tokens at rest; independent of `secretKey` (2.12.0); auto-generated unless set |
| `openwebui.databaseName` | Open WebUI's database on the shared PostgreSQL (default `openwebui`) |
| `openwebui.resources` | CPU / memory requests and limits |
| `openwebui.persistence.{enabled,size,storageClass}` | PVC for uploads and local cache |
| `openwebui.ingress.*` | Ingress / Gateway API configuration |
| `openwebui.env.*` | Environment passthrough (OAuth, banner text, feature flags) |

## High availability

Open WebUI is stateless only when its session and config state live in shared
backends, so the chart wires that up by default (per Open WebUI's
[Scaling & HA](https://docs.openwebui.com/) guidance):

- **`WEBUI_SECRET_KEY`** and **`OAUTH_SESSION_TOKEN_ENCRYPTION_KEY`** come from
  the generated `openwebui-secret` — two **independent** keys since 2.12.0
  (`secret-key` / `oauth-token-encryption-key`), both stable across restarts,
  so sessions stay valid and every replica signs tokens identically. (Upgrading
  from ≤2.11.x re-keys OAuth token encryption: SSO users re-authenticate once.)
- **`DATABASE_URL`** points at the shared PostgreSQL (`openwebui.databaseName`,
  auto-created in `standalone` mode) when `postgres.enabled=true`, replacing the
  single-pod SQLite file.
- **`REDIS_URL` + `WEBSOCKET_MANAGER=redis` + `WEBSOCKET_REDIS_URL`** use Valkey
  to coordinate websocket and config state across replicas (with
  `valkey.auth.enabled` the URLs embed the password from the valkey Secret —
  [ADR-008](../architecture/ADR-008-valkey-auth.md)).

To scale out, raise `openwebui.replicaCount` (or enable `openwebui.autoscaling`)
with `postgres.enabled=true` and `valkey.enabled=true` (both default on). For an
ephemeral single-pod lab, `postgres.enabled=false` falls back to SQLite.

## Integrations

Open WebUI talks to every T1/T2 service over in-cluster DNS:

- Ollama (`OLLAMA_BASE_URL`) — local inference
- Qdrant (`VECTOR_DB=qdrant`, `QDRANT_URI`) — vector retrieval
- Tika (`CONTENT_EXTRACTION_ENGINE`) — document text extraction
- SearXNG (`WEB_SEARCH_ENGINE`, opt-in via `ENABLE_WEB_SEARCH`; off by default) — web search
- Valkey — session cache
- MCPO, LangGraph, Open Terminal, external APIs — opt-in routes

## RAG retrieval

Open WebUI is the primary RAG surface; defaults and tuning live in
`openwebui.env.*` (full list in [`values.yaml`](../../values.yaml)):

- **Embedding task prefixes (on by default).** `RAG_EMBEDDING_QUERY_PREFIX`
  (`search_query: `) and `RAG_EMBEDDING_CONTENT_PREFIX` (`search_document: `)
  are required by the default `nomic-embed-text` embedder for good retrieval.
  The ingestion worker and Pydantic AI apply the matching prefixes, so a Qdrant
  collection stays consistent between its writer and reader. Clear both for a
  non-instruction-tuned embedder. **Changing a prefix or the embedding model
  changes the vector space — re-index existing knowledge afterwards.**
- **Hybrid search + reranking (opt-in, OFF by default).**
  `ENABLE_RAG_HYBRID_SEARCH` adds a BM25 lexical leg fused with the dense-vector
  results; `RAG_RERANKING_MODEL` enables a cross-encoder reranking stage
  (tuned by `RAG_TOP_K_RERANKER` and `RAG_HYBRID_BM25_WEIGHT`). The reranking
  model is **downloaded from Hugging Face at runtime**, so enabling it requires
  an egress grant (the default-deny NetworkPolicy blocks it) or pre-staging the
  model into the Open WebUI PVC. Recommended rerankers are small and Apache-2.0
  (`BAAI/bge-reranker-v2-m3`, `cross-encoder/ms-marco-MiniLM-L-6-v2`).

See [ADR-011](../architecture/ADR-011-rag-retrieval-quality.md) and
[HOWTO §4](../../HOWTO.md#4-rag-retrieval-augmented-generation).

## Security

- Runs as non-root (UID 1000), read-only root filesystem where upstream permits
- Dedicated ServiceAccount with `automountServiceAccountToken: false` ([POL-001](../governance/CONTROLS.md#policies-pol))
- Telemetry opt-out env vars (`DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY=false`) set by default
- AI Act Art. 50(1) transparency banner via `WEBUI_BANNERS` (a JSON banner list;
  the chart ships a default AI-disclosure banner)

## Reference architecture

Open WebUI is the entry point for the **conversational + RAG flow** described
in [docs/architecture/REFERENCE.md §2](../architecture/REFERENCE.md#2-conversational--rag-flow-open-webui).
Best-practice patterns:

- Treat all inference (Ollama, External APIs, LangGraph, Pydantic AI) as one OpenAI-compatible surface so the model picker handles routing.
- Use the bundled MCPO as the single tool gateway; do not let Open WebUI call internal services directly.
- Enable async ingestion (`ingestionWorker.enabled=true`) for bulk uploads so the chat path stays non-blocking.
- Front Open WebUI with Authelia OIDC and put MFA on the production policy.

## Related HOWTO sections

- [§2 Day-1 Setup](../../HOWTO.md#2-day-1-setup)
- [§4 RAG](../../HOWTO.md#4-rag-retrieval-augmented-generation)
- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
- [§9 MCP Tool Integration](../../HOWTO.md#9-mcp-tool-integration-mcpo)
- [§11 Ingress and TLS](../../HOWTO.md#11-ingress-and-tls)
- [§12 Authelia SSO/OIDC](../../HOWTO.md#12-authentication-with-authelia-sso--oidc)
