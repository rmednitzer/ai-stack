# LangGraph

LangGraph Platform runtime for stateful agentic workflows. Requires PostgreSQL for checkpoint persistence. Connects to Ollama, Qdrant, Tika, and SearXNG.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: opt-in (`langgraph.enabled=false`)
- **License**: **Elastic License 2.0 (ELv2)** — see [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md). Permits self-hosted use; prohibits offering as a managed service.
- **Upstream**: <https://langchain-ai.github.io/langgraph/> · [Platform docs](https://langchain-ai.github.io/langgraph/cloud/)
- **Default image**: `docker.io/langchain/langgraph-server` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/langgraph/`](../../templates/langgraph/)
- **MIT alternative**: see [Pydantic AI](pydanticai.md) for a fully-permissive agentic runtime (the `langgraph-server` image is ELv2 and needs a commercial key for production self-hosting — see [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md#source-available--langgraph-api-elastic-license-20)). Both share the same Ollama/Qdrant/SearXNG/Postgres/OTel integrations; enable either or both.

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `langgraph.enabled` | Toggle the component |
| `langgraph.image.{repository,tag}` | Container image override — typically a custom image with your graphs baked in |
| `langgraph.apiKey` | Explicit API key; otherwise auto-generated into `langgraph-secret` |
| `langgraph.graphsVolume.*` | Alternative to custom image — mount graph code from a PVC |
| `langgraph.postgres.*` | Connection settings (defaults to the in-cluster `postgres` component) |
| `langgraph.resources` | CPU / memory |

## Deploying your own graphs

1. **Custom image** (recommended): `langgraph build -t my-graphs:v1` and set `langgraph.image.repository`/`tag`.
2. **Volume mount**: drop graph source into `/deps/graphs` on the `graphsVolume` PVC.

## Dependencies

- `postgres.enabled: true` (any of `standalone`, `cnpg`, `external`)
- Ollama, Qdrant, Tika, SearXNG — all standard T1/T2 services the chart already wires up

## Reference architecture

LangGraph is the **agentic runtime** described in
[docs/architecture/REFERENCE.md §3](../architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).
Best-practice patterns:

- Always run with a Postgres checkpointer/store; do not run agents stateless.
- Reuse the chat tool catalog by routing tool calls through MCPO instead of bespoke clients.
- Use Qdrant for semantic memory and Postgres for structured agent state.
- Front LangGraph with Open WebUI (or your own UI) for auth and audit; do not expose it directly to end users.
- In production, use `postgres.mode: cnpg` for HA + PITR.

## Related HOWTO sections

- [§8 Agentic Workloads (LangGraph)](../../HOWTO.md#8-agentic-workloads-langgraph-or-pydantic-ai)
- [§9 MCP Tool Integration](../../HOWTO.md#9-mcp-tool-integration-mcpo)
- [§10 PostgreSQL Modes](../../HOWTO.md#10-postgresql-modes)
