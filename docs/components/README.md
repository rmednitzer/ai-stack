# Component Reference

Short reference pages for every component in the ai-stack chart. Each page summarises the component's purpose, tier, default image, key `values.yaml` knobs, NetworkPolicy allowlist, and links to upstream documentation. Full operational tasks live in [HOWTO.md](../../HOWTO.md); this directory is a navigation aid, not a replacement.

For the authoritative list of tiers and control references, see [../governance/CONTROLS.md](../governance/CONTROLS.md). For how the components compose into the conversational + RAG and agentic flows, see [../architecture/REFERENCE.md](../architecture/REFERENCE.md).

## Components by Tier

### T0 — Safety / Integrity

| Component | Default | Page |
|-----------|---------|------|
| OpenTelemetry Collector | enabled when `global.otel.enabled=true` | [otel.md](otel.md) |
| Authelia | opt-in | [authelia.md](authelia.md) |

### T1 — Operational

| Component | Default | Page |
|-----------|---------|------|
| Open WebUI | enabled | [openwebui.md](openwebui.md) |
| Ollama | enabled | [ollama.md](ollama.md) |
| Qdrant | enabled | [qdrant.md](qdrant.md) |
| LangGraph | opt-in | [langgraph.md](langgraph.md) |
| Pydantic AI | opt-in | [pydanticai.md](pydanticai.md) |
| Envoy AI Gateway | opt-in | [envoy-ai-gateway.md](envoy-ai-gateway.md) |

### T2 — Productivity

| Component | Default | Page |
|-----------|---------|------|
| Apache Tika | enabled | [tika.md](tika.md) |
| SearXNG | enabled | [searxng.md](searxng.md) |
| Valkey | enabled | [valkey.md](valkey.md) |
| PostgreSQL | enabled | [postgres.md](postgres.md) |
| Open Terminal | opt-in | [open-terminal.md](open-terminal.md) |
| MCPO | opt-in | [mcpo.md](mcpo.md) |
| Ingestion Worker | opt-in | [ingestion-worker.md](ingestion-worker.md) |
