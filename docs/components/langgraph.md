# LangGraph

LangGraph Platform runtime for stateful agentic workflows. Requires PostgreSQL for checkpoint persistence. Connects to Ollama, Qdrant, Tika, and SearXNG.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Default**: opt-in (`langgraph.enabled=false`)
- **License**: **Elastic License 2.0 (ELv2)** — see [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md). Permits self-hosted use; prohibits offering as a managed service.
- **Upstream**: <https://langchain-ai.github.io/langgraph/> · [Platform docs](https://langchain-ai.github.io/langgraph/cloud/)
- **Default image**: `docker.io/langchain/langgraph-server` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/langgraph/`](../../templates/langgraph/)

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

## Related HOWTO sections

- [§8 Agentic Workloads (LangGraph)](../../HOWTO.md#8-agentic-workloads-langgraph)
- [§10 PostgreSQL Modes](../../HOWTO.md#10-postgresql-modes)
