# MCPO

MCP-to-OpenAPI proxy. Exposes Model Context Protocol (MCP) servers as standard OpenAPI endpoints so Open WebUI (and other OpenAPI-aware tools) can use MCP tools without speaking MCP directly.

- **Tier**: T2 (productivity)
- **Boundary**: `internal`
- **Default**: opt-in (`mcpo.enabled=false`)
- **Upstream**: <https://github.com/open-webui/mcpo>
- **Default image**: `ghcr.io/open-webui/mcpo` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/mcpo/`](../../templates/mcpo/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `mcpo.enabled` | Toggle the component |
| `mcpo.image.{repository,tag}` | Container image override |
| `mcpo.apiKey` | Explicit API key; otherwise auto-generated into `mcpo-secret` |
| `mcpo.servers` | List of upstream MCP servers (command/args or URL) |
| `mcpo.resources` | CPU / memory |

## Security

- MCP servers can be arbitrarily powerful — treat `mcpo.servers` as privileged configuration
- NetworkPolicy egress allowlist must cover any remote MCP endpoints
- Per-tool auth handled by MCPO; require an API key on every request

## Reference architecture

MCPO is the **shared tool surface** for both Open WebUI chat and the agentic
runtimes (LangGraph / Pydantic AI) — see
[docs/architecture/REFERENCE.md §3](../architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).
Best-practice patterns:

- Author tools once as MCP servers; let MCPO surface them as OpenAPI for both the chat and agent paths.
- Treat `mcpo.servers` as privileged config — review like RBAC.
- Keep network egress for remote MCP endpoints in the NetworkPolicy allowlist.
- Require an API key on every request (auto-generated into `mcpo-secret` if not supplied).

## Related HOWTO sections

- [§9 MCP Tool Integration (MCPO)](../../HOWTO.md#9-mcp-tool-integration-mcpo)
