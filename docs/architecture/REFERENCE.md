# Reference Architecture — Open WebUI and Agentic Workloads

This document describes the reference architecture the chart composes and the
patterns it implements for two primary workloads: **conversational + RAG**
(Open WebUI) and **agentic** (LangGraph or Pydantic AI). It is the long-form companion to the
[architecture diagram in README.md](../../README.md#architecture).

The chart's job is to give you a defensible default topology — correct
defaults, sensible component boundaries, and clear extension points — not to
prescribe model or graph choices. Substitute components freely; the contracts
below are what matter.

## 1. Design principles

- **Stable interfaces, swappable implementations.** Every component exposes a
  protocol the rest of the stack already speaks (OpenAI Chat Completions, MCP,
  OTLP, Postgres wire protocol, Redis-compatible streams). No bespoke
  adapters live inside the chart.
- **One model surface.** Local (Ollama), hosted (External APIs), and agentic
  (LangGraph) all present an OpenAI-compatible endpoint. Open WebUI's model
  picker treats them uniformly.
- **One tool surface.** Tools are authored as MCP servers and surfaced through
  MCPO's MCP→OpenAPI gateway. The same tool definition is reachable from Open
  WebUI chat, from LangGraph agents, or from any OpenAPI-aware client.
- **Async by default at boundaries that matter.** Document ingestion is
  decoupled with Valkey Streams so uploads do not block the chat path.
- **Stateful agents need durable state.** LangGraph uses PostgreSQL as the
  checkpointer and store; semantic memory lives in Qdrant. Both can run in HA.
- **Defence in depth, telemetry by default.** PSA `restricted`, default-deny
  NetworkPolicies, per-component ServiceAccounts, OIDC at the edge, and an
  OTel collector with PII redaction are on the recommended path.

## 2. Conversational + RAG flow (Open WebUI)

```text
Client → Ingress → (Authelia OIDC) → Open WebUI
  ├─ inference         → Ollama | External APIs | LangGraph     (OpenAI API)
  ├─ retrieval         → Qdrant                                  (vector search)
  ├─ extract on upload → Tika                                    (sync)
  ├─ web fallback      → SearXNG
  ├─ tools             → MCPO → MCP servers
  ├─ sessions          → Valkey
  └─ async ingest      → Valkey Stream → Ingestion Worker → Tika → Ollama → Qdrant
```

### What's important

| Concern | Pattern | Why |
|---------|---------|-----|
| Model routing | OpenAI-compatible endpoints only | Lets users pick any model from one picker; vendor-neutral |
| Embeddings | Served by Ollama (or any OpenAI-compat embedding endpoint) | Same auth/network surface as inference |
| Document upload | Synchronous Tika extract for small files; **async path for batch** | Keeps p50 latency tight; large or many uploads do not block UI |
| Web search | SearXNG behind the chart, not a third-party API | No data egress to ad-tech crawlers; aligns with EU operations |
| Tool use | MCPO front-ends MCP servers as OpenAPI | Open WebUI consumes OpenAPI natively; agents reuse the same tools |
| Identity | Authelia OIDC; Open WebUI as relying party | Centralised MFA, single audit trail |

### When to enable async ingestion

Default to async (`ingestionWorker.enabled=true`) when any of the following
applies:

- Bulk document loads (more than ~10 docs at a time)
- Files larger than ~10 MB
- Pipelines that need retries, dead-lettering, or audit
- A separate scaling profile from the chat path is desired

The Ingestion Worker reads a Valkey Stream (`ingestion:documents`), runs Tika
extract → chunk → Ollama embed → Qdrant upsert, and writes status to
`ingestion:status:<task_id>`. See
[HOWTO §5](../../HOWTO.md#5-async-document-ingestion) for the producer
contract.

## 3. Agentic flow (LangGraph or Pydantic AI)

The chart ships two interchangeable agentic runtimes that implement the **same
contracts** — PostgreSQL for durable state, Qdrant for semantic memory, MCPO for
the shared tool catalog, Ollama/External APIs for inference, and Open WebUI as
the front door. Choose by licensing and execution model:

- **LangGraph** — graph-based orchestration. The `langgraph-server` image is
  Elastic License 2.0; production self-hosting needs a commercial LangGraph
  Platform key (see [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md#source-available--langgraph-api-elastic-license-20)).
- **Pydantic AI** — type-safe agents with durable execution via DBOS, checkpointed
  in the same PostgreSQL; fully MIT/Apache-2.0. See [pydanticai.md](../components/pydanticai.md).

The flow below is drawn for LangGraph; the Pydantic AI runtime substitutes the
LangGraph box (DBOS provides the checkpointer/store) and keeps every other edge
identical.

```text
Open WebUI ─(OpenAI API)→ LangGraph
                              │
                              ├─ inference        → Ollama | External APIs
                              ├─ semantic memory  → Qdrant
                              ├─ tools            → MCPO → MCP servers
                              ├─ web              → SearXNG
                              ├─ sandbox exec     → Open Terminal (opt-in)
                              └─ checkpointer/store → PostgreSQL (CNPG in prod)
```

### What's important

| Concern | Pattern | Why |
|---------|---------|-----|
| State | Postgres checkpointer + store | Resumable graphs, HITL pause/resume, observability across runs |
| Long-term memory | Qdrant for semantic; Postgres for structured | Each store does what it's good at |
| Tool catalog | Shared with Open WebUI via MCPO | One source of truth for tool definitions and auth |
| Inference | Same OpenAI-compatible surface as chat | Swap models per-graph or per-node without rewiring |
| Sandboxed exec | Open Terminal, not arbitrary shells | Bounded blast radius; PSA-compatible |
| HA database | CloudNativePG (`postgres.mode=cnpg`) | Streaming replication, automated failover, Barman PITR |

### Anti-patterns

- **Don't bypass MCPO and let agents call internal services directly.** You lose
  the shared tool catalog, the per-tool auth boundary, and the audit surface.
- **Don't store long-running agent state in Valkey.** Valkey is cache and
  streams; checkpoints belong in Postgres.
- **Don't run agents without durable state.** Without a checkpointer (LangGraph)
  or DBOS durable execution (Pydantic AI), HITL, retries, and observability
  across steps degrade to a single-shot RPC.
- **Don't expose the agent runtime directly to end users.** Front it with Open WebUI
  (or your own UI) so authentication, audit, and rate limiting are consistent.

## 4. Cross-cutting concerns

### Identity (Authelia)

Authelia sits at the edge as an OIDC provider. Open WebUI is auto-wired as a
relying party when `authelia.enabled=true`. Storage is SQLite (lab) or
PostgreSQL (`authelia.storage=postgres`); session state is Valkey when
available, in-memory otherwise. This means Authelia → Valkey and
Authelia → Postgres are **conditional** edges in the diagram.

### Observability (OTel)

The collector applies GenAI semantic conventions and PII redaction (emails,
SSNs, credit-card numbers) before exporting. All instrumented components emit
OTLP to it; ServiceMonitor resources are optional for Prometheus integration.

### Network and pod security

Default-deny NetworkPolicies with per-component allowlists. PSA `restricted`
baseline (`runAsNonRoot`, `seccompProfile: RuntimeDefault`,
`allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`). Read-only root
filesystem where upstream permits. Per-component ServiceAccounts with
`automountServiceAccountToken: false`.

### Persistence and HA

| Tier | Standalone | HA recommendation |
|------|------------|-------------------|
| Postgres | `mode: standalone` (lab) | `mode: cnpg` with 3 instances + PgBouncer |
| Qdrant | single replica | replica set with sharding when collections grow |
| Valkey | single replica + persistence | replicated Valkey or Sentinel for prod |
| Ollama | one replica per GPU | per-GPU StatefulSet; pull models out of band |
| Open WebUI | single replica + RWO PVC | multi-replica + RWX or external Postgres backend |

## 5. Production hardening checklist

Use this as the gate for moving from `lab` to `prod`:

- [ ] `global.profile: prod` and `-f values-prod.yaml` applied
- [ ] `global.podSecurityStandard: restricted` (default)
- [ ] `global.networkPolicy.enabled: true` (default)
- [ ] `global.otel.enabled: true` and a real OTLP backend wired
- [ ] `authelia.enabled: true` with MFA (`defaultPolicy: two_factor`)
- [ ] Ingress with TLS (cert-manager or external CA); `Strict-Transport-Security` enforced
- [ ] Postgres in `cnpg` mode (or `external`) with backups configured
- [ ] Qdrant API key sourced from external secret store (ESO, Vault)
- [ ] Ollama on dedicated GPU nodes with taints/tolerations
- [ ] LangGraph + `ingestionWorker.enabled` on the agentic path; Valkey persistence on
- [ ] Open WebUI banner text set (AI Act Art. 50(1) transparency)
- [ ] CycloneDX SBOM (`sbom.cdx.json`) cross-checked against deployed images
- [ ] PrometheusRule alerts wired (see `templates/common/`)
- [ ] Velero + CSI snapshots for PVC-backed data; CNPG Barman for Postgres PITR

## 6. Extension points

The chart deliberately stops at the contracts below; extend at these seams.

| Extension | How |
|-----------|-----|
| Add a new MCP tool | Append to `mcpo.config.mcpServers`; tool surfaces in Open WebUI and LangGraph automatically |
| Add a hosted model provider | Append to `externalAPIs.providers`; appears in Open WebUI's model picker |
| Replace embeddings | Point Open WebUI / Ingestion Worker at a different OpenAI-compatible embedding endpoint |
| Custom LangGraph graphs | Build with `langgraph build` and override `langgraph.image` (recommended), or mount via `langgraph.graphsVolume` |
| External vector DB | Set Open WebUI / LangGraph / Ingestion Worker env to point at the external endpoint; disable bundled Qdrant |
| External Postgres | `postgres.mode: external` with secret reference |

## 7. Related reading

- [README — Architecture](../../README.md#architecture) — diagram and tier table
- [HOWTO — Agentic Workloads](../../HOWTO.md#8-agentic-workloads-langgraph-or-pydantic-ai)
- [HOWTO — MCP Tool Integration](../../HOWTO.md#9-mcp-tool-integration-mcpo)
- [HOWTO — Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
- [HOWTO — RAG](../../HOWTO.md#4-rag-retrieval-augmented-generation)
- [Component Reference](../components/README.md)
- [Governance Controls](../governance/CONTROLS.md)
- [License Compliance](../compliance/LICENSE_COMPLIANCE.md)
