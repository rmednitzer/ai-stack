# MCPO

MCP-to-OpenAPI proxy. Exposes Model Context Protocol (MCP) servers as standard OpenAPI endpoints so Open WebUI (and other OpenAPI-aware tools) can use MCP tools without speaking MCP directly.

- **Tier**: T2 (productivity)
- **Boundary**: `decision`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
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
| `mcpo.config.mcpServers` | Map of upstream MCP servers (Claude Desktop config format: `command`/`args` for stdio, or a URL for SSE/streamable-http) |
| `mcpo.runtimeClassName` | Sandbox runtime (e.g. `gvisor`, `kata`) for stdio MCP subprocesses. Empty = cluster default. |
| `mcpo.resources` | CPU / memory |

## Security

MCPO is the **shared tool gateway** for the chat and agent paths: every tool
call flows through it. Threat-model it as a privileged proxy, not a passthrough.

- **Treat `mcpo.config.mcpServers` as privileged config — review it like RBAC.**
  An MCP server can be arbitrarily powerful; only wire servers you trust.
- **Isolate stdio subprocesses.** MCPO spawns `command`/`args` MCP servers in
  its pod. Set `mcpo.runtimeClassName` (`gvisor`/`kata`) when those servers run
  untrusted code, and keep `resources.limits` tight.
- **Network egress allowlist** must cover any remote (SSE/streamable-http) MCP
  endpoints; the chart's NetworkPolicy is default-deny with HTTP/HTTPS egress.
- **Require an API key on every request** (auto-generated into `mcpo-secret`).
  The static key gives no per-client identity, rotation, or audience binding —
  the MCP authorization spec's model for HTTP-exposed servers is OAuth 2.1
  (PKCE + audience-bound tokens). If you expose MCPO beyond the cluster via the
  gateway/ingress, front that route with **Authelia** (already shipped) using a
  ForwardAuth / OIDC policy rather than relying on the shared key alone. By
  default MCPO is `ClusterIP` (in-cluster only); the API key + NetworkPolicy are
  the baseline, not the target.
- **No token passthrough.** When MCPO calls an upstream API, that hop must use
  its own credential — do not forward the caller's token (MCP "confused deputy"
  guidance).
- **Audit.** With `global.otel.enabled=true`, tool-call telemetry is traced and
  secrets are redacted before export; ship it off-cluster for a durable record.

> Note: the NetworkPolicy ingress allow-list currently admits Open WebUI (and
> the connection-test pod). If you route the agent runtimes (LangGraph /
> Pydantic AI) through MCPO as well, confirm their access is intended before
> widening the allow-list — least privilege over convenience.

## Reference architecture

MCPO is the **shared tool surface** for both Open WebUI chat and the agentic
runtimes (LangGraph / Pydantic AI) — see
[docs/architecture/REFERENCE.md §3](../architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).
Best-practice patterns:

- Author tools once as MCP servers; let MCPO surface them as OpenAPI for both the chat and agent paths.
- Treat `mcpo.config.mcpServers` as privileged config — review like RBAC.
- Keep network egress for remote MCP endpoints in the NetworkPolicy allowlist.
- Require an API key on every request (auto-generated into `mcpo-secret` if not supplied).

## Related HOWTO sections

- [§9 MCP Tool Integration (MCPO)](../../HOWTO.md#9-mcp-tool-integration-mcpo)
