# Open WebUI

Primary user-facing chat UI and orchestrator for the ai-stack. Handles authentication, conversation state, model selection (local and external), RAG document upload, and routing to Ollama, Qdrant, Tika, SearXNG, MCPO, and LangGraph.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
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
| `openwebui.resources` | CPU / memory requests and limits |
| `openwebui.persistence.{enabled,size,storageClass}` | PVC for database, uploads, memories |
| `openwebui.ingress.*` | Ingress / Gateway API configuration |
| `openwebui.env.*` | Environment passthrough (OAuth, banner text, feature flags) |

## Integrations

Open WebUI talks to every T1/T2 service over in-cluster DNS:

- Ollama (`OLLAMA_BASE_URL`) — local inference
- Qdrant (`RAG_VECTOR_DB`) — vector retrieval
- Tika (`CONTENT_EXTRACTION_ENGINE`) — document text extraction
- SearXNG (`RAG_WEB_SEARCH_ENGINE`) — web search
- Valkey — session cache
- MCPO, LangGraph, Open Terminal, external APIs — opt-in routes

## Security

- Runs as non-root (UID 1000), read-only root filesystem where upstream permits
- Dedicated ServiceAccount with `automountServiceAccountToken: false` ([POL-001](../governance/CONTROLS.md#policies-pol))
- Telemetry opt-out env vars (`DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY=false`) set by default
- AI Act Art. 50(1) transparency banner via `WEBUI_BANNER_TEXT`

## Reference architecture

Open WebUI is the entry point for the **conversational + RAG flow** described
in [docs/architecture/REFERENCE.md §2](../architecture/REFERENCE.md#2-conversational--rag-flow-open-webui).
Best-practice patterns:

- Treat all inference (Ollama, External APIs, LangGraph) as one OpenAI-compatible surface so the model picker handles routing.
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
