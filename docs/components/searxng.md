# SearXNG

Privacy-respecting metasearch engine used by Open WebUI and LangGraph for web search in RAG workflows.

- **Tier**: T2 (productivity)
- **Boundary**: `internal`
- **Default**: enabled
- **License**: **AGPL-3.0** — see [LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md) for copyleft analysis
- **Upstream**: <https://docs.searxng.org/>
- **Default image**: `searxng/searxng` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/searxng/`](../../templates/searxng/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `searxng.enabled` | Toggle the component |
| `searxng.image.{repository,tag}` | Container image override |
| `searxng.secretKey` | Explicit secret; otherwise auto-generated into `searxng-secret` |
| `searxng.settings.*` | SearXNG engine configuration (rendered into `settings.yml`) |
| `searxng.resources` | CPU / memory |

## Security

- Read-only root filesystem enforced
- Egress NetworkPolicy allows only HTTPS (443) to search engines
- No query logging; session state held in Valkey when enabled

## Licensing note

SearXNG is AGPL-3.0. Running the upstream container unmodified as an internal service is low risk. If you **modify** SearXNG and expose it to users over a network, AGPL source-disclosure obligations apply.

## Related HOWTO sections

- [§4.4 Enable web search](../../HOWTO.md#44-enable-web-search)
