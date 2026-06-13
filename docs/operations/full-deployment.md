# Full deployment — everything wired into Open WebUI

This guide deploys the **complete** ai-stack: every component enabled and wired
through Open WebUI, including the async ingestion worker, the Pydantic AI agent,
SearXNG web search, and the tool gateway. It pairs with
[`values-full.yaml`](../../values-full.yaml).

```bash
helm install ai-stack . -f values.yaml -f values-full.yaml \
  -n ai-stack --create-namespace
```

`values-full.yaml` is **feature-complete, not hardened-for-HA**. For production,
also layer [`values-prod.yaml`](../../values-prod.yaml) (HA CloudNativePG,
topology spread, tighter limits) and apply the operator-owned controls in the
[hardening guide](hardening-guide.md):

```bash
helm install ai-stack . -f values.yaml -f values-full.yaml -f values-prod.yaml \
  -n ai-stack --create-namespace
```

## What the overlay turns on

| Component | Role | Wired into Open WebUI as |
|-----------|------|--------------------------|
| Ollama | Local model inference + embeddings | OpenAI-compatible model endpoint |
| Qdrant | Vector store | `VECTOR_DB=qdrant` (native RAG) + the agent's retrieval tool |
| Tika | Document text extraction | `CONTENT_EXTRACTION_ENGINE=tika` (native RAG) + the worker |
| SearXNG | Web search backend | `WEB_SEARCH_ENGINE=searxng` (enabled here) |
| Ingestion worker | Async bulk document ingestion | via the Pydantic AI agent (see below) |
| Pydantic AI | Agent runtime (MIT) with RAG + web tools | a model in the picker (`pydanticai-agent`) |
| PostgreSQL | Shared state (Open WebUI, agent durability, corpus state) | `DATABASE_URL` |
| Valkey | Session/websocket coordination + the ingestion stream | `REDIS_URL` |
| OTel Collector | Observability with secret/PII redaction | telemetry sink |

Operator-specific edges are left as ready-to-enable blocks in the overlay: MCPO
(tool gateway), LangGraph (alternative agent, Elastic-licensed), and Authelia
(OIDC SSO). See the sections below.

## Prerequisite: pull the Ollama models

Ollama does not auto-pull. The full overlay's agent uses `llama3.2`, and RAG uses
the `nomic-embed-text` embedder. Pull both into the running Ollama pod:

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull llama3.2
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull nomic-embed-text
```

Use a GPU node and size `ollama.resources` for your models in production.

## The two RAG paths

The stack has **two distinct retrieval paths into the same Qdrant**. Knowing
which is which avoids the common "I uploaded a doc but the agent can't see it"
confusion.

### Path 1 — Open WebUI native RAG (interactive uploads)

A user uploads a file in the Open WebUI UI (or attaches it to a chat). Open WebUI
extracts it with Tika, embeds it with Ollama, and stores it in **its own**
Qdrant collections (named per Open WebUI knowledge base / file id). Retrieval is
automatic for that chat/knowledge base. This path is self-contained in Open WebUI
and needs no worker.

### Path 2 — Ingestion worker → Pydantic AI agent (bulk / automated)

For bulk or automated ingestion, a producer enqueues documents on a Valkey stream;
the worker processes them into a **single shared collection** (`documents`), and
the **Pydantic AI agent** answers over that collection through its
`search_knowledge_base` tool. Because `pydanticai.exposeToOpenWebUI=true`, the
agent appears as the model **`pydanticai-agent`** in Open WebUI's picker. So:

```
producer --XADD--> Valkey stream --> ingestion worker
   --> Tika extract --> Ollama embed --> Qdrant "documents" collection
        ^ same collection v
Open WebUI (pick the "pydanticai-agent" model) --> Pydantic AI agent
   --> search_knowledge_base tool --> Qdrant "documents" --> grounded answer
```

The writer (worker) and reader (agent) are kept consistent by the chart: both use
`QDRANT_COLLECTION=documents` and the paired `nomic-embed-text` task prefixes
(`search_document: ` on write, `search_query: ` on read). **Changing the
embedding model or a prefix changes the vector space — re-index afterwards**
(ADR-011).

> The worker is **not** driven by Open WebUI uploads — it is a separate, scalable
> ingestion lane. To make documents that a worker ingested answerable in Open
> WebUI, chat with the `pydanticai-agent` model. To answer over an interactive
> upload, use Path 1.

### Feeding the ingestion worker

Producers enqueue tasks with `XADD`; the worker fetches the source, extracts,
embeds, and upserts. Minimal example (full reference, including per-tenant tags
and source connectors, in [HOWTO §5](../../HOWTO.md#5-async-document-ingestion)):

```bash
kubectl exec -n ai-stack deploy/ai-stack-valkey -- \
  valkey-cli XADD ingestion:documents '*' \
    task_id doc-001 \
    file_url https://example.com/report.pdf \
    filename report.pdf
```

Per-tenant isolation and GDPR erasure (tag `user_id` / `tenant_id`) are covered in
[the ingestion-worker spec](../components/ingestion-worker-spec.md) and runbook A6.

## Web search

`values-full.yaml` sets `ENABLE_WEB_SEARCH=true`, making the (already-running)
SearXNG backend usable from Open WebUI. The base chart keeps it **off**: web
content is attacker-influenced (indirect prompt injection — see
[SECURITY.md](../../SECURITY.md)), so enabling the web attack surface is a
deliberate opt-in. Pydantic AI exposes a matching `web_search` tool over the same
SearXNG. Pair with the FQDN egress control in the
[hardening guide](hardening-guide.md) to bound where web fetches can go.

## MCPO tool gateway (operator step)

MCPO turns MCP servers into OpenAPI tool servers Open WebUI can call. Two things
are required, and one is deliberately manual:

1. **Configure your MCP servers** under `mcpo.config.mcpServers` and set
   `mcpo.enabled=true` (see the commented block in `values-full.yaml`).
2. **Connect Open WebUI to MCPO in the admin UI**, not via env. Open WebUI's
   `TOOL_SERVER_CONNECTIONS` embeds the tool-server API key as inline JSON; the
   chart will **not** bake MCPO's key into the Open WebUI pod manifest as
   plaintext (that would violate POL-002, no inline credentials). Instead:
   - Get the MCPO key:
     `kubectl get secret -n ai-stack ai-stack-mcpo-secret -o jsonpath='{.data.api-key}' | base64 -d`
   - In Open WebUI: **Settings → Tools → Add Connection**, URL
     `http://ai-stack-mcpo:8000/<server-name>`, auth Bearer, paste the key. Open
     WebUI stores it in its database, not a pod spec.

## LangGraph (optional, licensed)

LangGraph is an alternative agent runtime. Its server image is **Elastic License
2.0** — production self-hosting needs a commercial key
([LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md)). Pydantic AI (MIT,
enabled above) is the unencumbered path. To enable LangGraph, uncomment its block
in `values-full.yaml`; it shares the same Ollama / Qdrant / SearXNG / Postgres
surface and is wired into Open WebUI the same way (an OpenAI-compatible model).

## Authelia SSO (operator step)

OIDC single sign-on is environment-specific (your domain, issuer URL, TLS,
ingress). Configure `authelia.oidc.*` and your ingress/Gateway, then enable the
Authelia block in `values-full.yaml`. The chart wires Open WebUI's `OAUTH_*` env
(client id, secret from the Authelia Secret, issuer URL, scopes) automatically.
See [HOWTO §12](../../HOWTO.md#12-authentication-with-authelia-sso--oidc).

## Security posture of the full deployment

Enabling this overlay turns on the **model-driven attack surface** the base chart
ships off (web search, agent tool-use, and — when you enable it — MCPO tool
execution). The threat model treats model/RAG/web/tool content as
attacker-influenced ([SECURITY.md](../../SECURITY.md)). The chart's floor still
applies (PodSecurity `restricted`, default-deny NetworkPolicy, per-component
ServiceAccounts, redaction). On top of it, for a full deployment:

- Apply the [hardening guide](hardening-guide.md): FQDN egress (B6) to bound web
  fetches and tool egress, a hardened `runtimeClassName` for MCPO if you run tool
  servers, image-signature admission (B5), and mTLS (B7).
- Front Open WebUI (and any exposed agent/MCPO route) with Authelia OIDC.
- Keep the blocking CVE gate green and review `LIMITATIONS.md`.

## Verify the deployment

```bash
# All workloads Ready
kubectl get pods -n ai-stack

# Open WebUI sees Ollama + the agent as models
kubectl exec -n ai-stack deploy/ai-stack-openwebui -- \
  sh -c 'echo "$OPENAI_API_BASE_URLS"'   # ...ollama:11434;...pydanticai:8000/v1

# Enqueue a doc, then ask the pydanticai-agent model about it in the UI.
```

## Related

- [HOWTO](../../HOWTO.md) — task-oriented recipes (RAG, ingestion, MCP, SSO, TLS)
- [Hardening guide](hardening-guide.md) — supply-chain + runtime controls (B4–B7)
- [Remediation runbook](RUNBOOK-remediation.md) — findings and their fixes
- [Architecture reference](../architecture/REFERENCE.md) — component flows
