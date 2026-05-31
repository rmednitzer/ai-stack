# Pydantic AI

Self-hosted [Pydantic AI](https://ai.pydantic.dev/) agent server with durable
execution via [DBOS](https://www.dbos.dev/) (checkpointed in the shared
PostgreSQL). Provided as a **fully MIT/Apache-2.0-licensed alternative** to the
LangGraph runtime, whose server image is Elastic License 2.0 and gates
production self-hosting behind a commercial key (see
[LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md#source-available--langgraph-api-elastic-license-20)).
Enable either or both — they share the same Ollama, Qdrant, SearXNG, and OTel
surface.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Default**: opt-in (`pydanticai.enabled=false`)
- **License**: MIT/Apache-2.0 throughout (Pydantic AI, DBOS, FastAPI; `uv`/Python base image)
- **Upstream**: <https://ai.pydantic.dev/> · [DBOS durable execution](https://ai.pydantic.dev/durable_execution/dbos/)
- **Default image**: `ghcr.io/astral-sh/uv` (uv + Python; see `values.yaml` for pinned tag)
- **Chart path**: [`templates/pydanticai/`](../../templates/pydanticai/) · agent source: [`files/pydanticai/app.py`](../../files/pydanticai/app.py)

## API

- `GET /health` — liveness/readiness.
- `POST /run` — body `{"prompt": "...", "thread_id": "optional"}` → runs the agent and returns `{"output", "durable"}`. When `pydanticai.apiKey` is set, requires `Authorization: Bearer <key>`.

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `pydanticai.enabled` | Toggle the component |
| `pydanticai.image.{repository,tag}` | Base image (uv/Python) or a prebuilt image |
| `pydanticai.buildDeps` | `true` (default): install deps at startup via initContainer. `false`: deps baked into the image ([Dockerfile](../../files/pydanticai/Dockerfile)) |
| `pydanticai.apiKey` | Explicit API key; otherwise auto-generated into `pydanticai-secret` (enforced on `POST /run`) |
| `pydanticai.env.AGENT_MODEL` | Ollama model the agent uses (pull it first) |
| `pydanticai.env.AGENT_SYSTEM_PROMPT` | System prompt / instructions |
| `pydanticai.autoscaling.*` | HPA settings |
| `pydanticai.resources` | CPU / memory |

## Extending the agent

The agent in `files/pydanticai/app.py` is a deliberately small **reference**:

- It wires an Ollama model (OpenAI-compatible) plus optional `web_search`
  (SearXNG) and `search_knowledge_base` (Qdrant) tools, registered only when
  those services are configured.
- For full durability of tool I/O under DBOS, decorate tool bodies with
  `@DBOS.step`.
- Add structured output types, MCP servers, or more tools, then either let the
  initContainer install your deps (`requirements.txt`) or bake a prebuilt image.

## Dependencies

- `postgres.enabled: true` (recommended) — DBOS checkpoints durable runs there; without it the agent runs **non-durable** (no resume).
- Ollama (inference); optionally Qdrant (retrieval tool) and SearXNG (web-search tool).

## Reference architecture

Pydantic AI is an alternative **agentic runtime** to the one described in
[docs/architecture/REFERENCE.md §3](../architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).
Best-practice patterns carry over:

- Run with a Postgres-backed durable executor (DBOS); do not run agents stateless in production.
- Use Qdrant for semantic memory and Postgres for durable workflow state.
- Front it with Open WebUI (or your own UI) for auth and audit; do not expose it directly to end users.
- In production, use `postgres.mode: cnpg` for HA + PITR.

## Related HOWTO sections

- [§8 Agentic Workloads](../../HOWTO.md#8-agentic-workloads-langgraph-or-pydantic-ai)
- [§9 MCP Tool Integration](../../HOWTO.md#9-mcp-tool-integration-mcpo)
- [§10 PostgreSQL Modes](../../HOWTO.md#10-postgresql-modes)
